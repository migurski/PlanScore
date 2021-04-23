''' Functions used for scoring district symmetry.

When all districts are added up and present on S3, performs complete scoring
of district plan and uploads summary JSON file.
'''
import io, os, gzip, posixpath, json, statistics, copy, time, itertools
import math
import argparse
import urllib.request
import pprint
import boto3, botocore.exceptions
from . import data, constants, matrix

FIELD_NAMES = (
    # Toy fields
    'Voters', 'Blue Votes', 'Red Votes',
    'Population', 'Voting-Age Population', 'Black Voting-Age Population',
    'US Senate Rep Votes', 'US Senate Dem Votes', 'US House Rep Votes', 'US House Dem Votes',
    'SLDU Rep Votes', 'SLDU Dem Votes', 'SLDL Rep Votes', 'SLDL Dem Votes',

    # Real fields
    'Democratic Votes', 'Republican Votes', 'Democratic Wins',
    
    # ACS 2015 fields
    'Black Population 2015', 'Black Population 2015, Error',
    'Hispanic Population 2015', 'Hispanic Population 2015, Error',
    'Population 2015', 'Population 2015, Error',
    'Voting-Age Population 2015', 'Voting-Age Population 2015, Error',
    
    # ACS 2016 fields
    'Black Population 2016', 'Black Population 2016, Error',
    'Hispanic Population 2016', 'Hispanic Population 2016, Error',
    'Population 2016', 'Population 2016, Error',
    'Voting-Age Population 2016', 'Voting-Age Population 2016, Error',
    'Education Population 2016', 'Education Population 2016, Error',
    'High School or GED 2016', 'High School or GED 2016, Error',
    'Households 2016', 'Households 2016, Error',
    'Household Income 2016', 'Household Income 2016, Error',
    
    # ACS 2018 fields
    'Black Population 2018', 'Black Population 2018, Margin',
    'Hispanic Population 2018', 'Hispanic Population 2018, Margin',
    'Population 2018', 'Population 2018, Margin',
    'Voting-Age Population 2018', 'Voting-Age Population 2018, Margin',
    #'Education Population 2018', 'Education Population 2018, Margin',
    'High School or GED 2018', 'High School or GED 2018, Margin',
    #'Households 2018', 'Households 2018, Margin',
    'Household Income 2018', 'Household Income 2018, Margin',
    'Citizen Voting-Age Population 2018', 'Citizen Voting-Age Population 2018, Margin',
    
    # ACS 2019 fields
    'Black Population 2019', 'Black Population 2019, Margin',
    'Hispanic Population 2019', 'Hispanic Population 2019, Margin',
    'Population 2019', 'Population 2019, Margin',
    'Voting-Age Population 2019', 'Voting-Age Population 2019, Margin',
    #'Education Population 2019', 'Education Population 2019, Margin',
    'High School or GED 2019', 'High School or GED 2019, Margin',
    #'Households 2019', 'Households 2019, Margin',
    'Household Income 2019', 'Household Income 2019, Margin',
    'Citizen Voting-Age Population 2019', 'Citizen Voting-Age Population 2019, Margin',
    
    # CVAP 2015 fields
    'Citizen Voting-Age Population 2015',
    'Citizen Voting-Age Population 2015, Error',
    'Black Citizen Voting-Age Population 2015',
    'Black Citizen Voting-Age Population 2015, Error',
    'Hispanic Citizen Voting-Age Population 2015',
    'Hispanic Citizen Voting-Age Population 2015, Error',
    
    # Census 2010 fields
    'Population 2010',
    
    # Fields for new unified, district-level plans
    'US President 2016 - DEM', 'US President 2016 - REP',
    'US President 2020 - DEM', 'US President 2020 - REP',
    
    # Extra fields
    'US Senate 2016 - DEM', 'US Senate 2016 - REP',
    )

# Fields for "DEM000"-style simulated election vote totals from 2018 and 2019 PlanScore models.
FIELD_NAMES += tuple([f'REP{sim:03d}' for sim in range(1000)])
FIELD_NAMES += tuple([f'DEM{sim:03d}' for sim in range(1000)])

# Template for simulated election vote totals with incumbency
FIELD_TMPL = '{incumbent}:{party}{sim:03d}'

# Fields for "O:DEM000"-style simulated election vote totals from PlanScore models starting 2020.
for (party, incumbent) in itertools.product(('DEM', 'REP'), list(data.Incumbency)):
    kwargs = dict(incumbent=incumbent.value, party=party)
    FIELD_NAMES += tuple([FIELD_TMPL.format(sim=sim, **kwargs) for sim in range(1000)])

def swing_vote(red_districts, blue_districts, amount):
    ''' Swing the vote by a percentage, positive toward blue.
    '''
    if amount == 0:
        return list(red_districts), list(blue_districts)
    
    districts = [(R, B, R + B) for (R, B) in zip(red_districts, blue_districts)]
    swung_reds = [((R/T - amount) * T) for (R, B, T) in districts if T > 0]
    swung_blues = [((B/T + amount) * T) for (R, B, T) in districts if T > 0]
    
    return swung_reds, swung_blues

def calculate_EG(red_districts, blue_districts, vote_swing=0):
    ''' Convert two lists of district vote counts into an EG score.
    
        By convention, result is positive for blue and negative for red.
    '''
    election_votes, wasted_red, wasted_blue, red_wins, blue_wins = 0, 0, 0, 0, 0
    red_districts, blue_districts = swing_vote(red_districts, blue_districts, vote_swing)
    
    # Calculate Efficiency Gap using swung vote
    for (red_votes, blue_votes) in zip(red_districts, blue_districts):
        district_votes = red_votes + blue_votes
        election_votes += district_votes
        win_threshold = district_votes / 2
        
        if red_votes > blue_votes:
            red_wins += 1
            wasted_red += red_votes - win_threshold # surplus
            wasted_blue += blue_votes # loser
        elif blue_votes > red_votes:
            blue_wins += 1
            wasted_blue += blue_votes - win_threshold # surplus
            wasted_red += red_votes # loser
        else:
            pass # raise ValueError('Unlikely 50/50 split')

    # Return an efficiency gap
    if election_votes == 0:
        return
    
    ## TODO: remove print output unless running planscore-score-locally
    #with open('EGs.csv', 'a') as file:
    #    print(f'{wasted_red:.2f},{wasted_blue:.2f}', file=file)
    
    return (wasted_red - wasted_blue) / election_votes

def calculate_MMD(red_districts, blue_districts):
    ''' Convert two lists of district vote counts into a Mean-Median score.
    
        By convention, result is positive for blue and negative for red.
    
        Vote swing does not seem to affect Mean-Median, so leave it off.
    '''
    shares = sorted([B/(R + B) for (R, B) in zip(red_districts, blue_districts)])
    
    median = statistics.median(shares)
    mean = statistics.mean(shares)
    
    ## TODO: remove print output unless running planscore-score-locally
    #with open('MMDs.csv', 'a') as file:
    #    print(f'{mean:.9f},{median:.9f}', file=file)
    
    return median - mean

def calculate_PB(red_districts, blue_districts):
    ''' Convert two lists of district vote counts into a Partisan Bias score.
    
        By convention, result is positive for blue and negative for red.
    '''
    red_total, blue_total = sum(red_districts), sum(blue_districts)
    blue_margin = (blue_total - red_total) / (blue_total + red_total)
    
    reds_5050, blues_5050 = swing_vote(red_districts, blue_districts, -blue_margin/2)
    blue_seats = len([True for (R, B) in zip(reds_5050, blues_5050) if R < B])
    blue_seatshare = blue_seats / len(blues_5050)
    blue_voteshare = sum(blues_5050) / (sum(blues_5050) + sum(reds_5050))

    assert round(blue_voteshare, 7) == .5, \
        'Vote-share Partisan Bias should always be 50%, not {}'.format(blue_voteshare)

    ## TODO: remove print output unless running planscore-score-locally
    #with open('PBs.csv', 'a') as file:
    #    print(f'{blue_seatshare:.9f},{blue_voteshare:.3f}', file=file)
    
    return blue_seatshare - blue_voteshare

def calculate_bias(upload):
    ''' Calculate partisan metrics for districts with plain vote counts.
        
        Look for obsolete vote properties from early 2018 PlanScore models.
    '''
    summary_dict, gaps = {}, {
        'Red/Blue': ('Red Votes', 'Blue Votes'),
        'US House': ('US House Rep Votes', 'US House Dem Votes'),
        'SLDU': ('SLDU Rep Votes', 'SLDU Dem Votes'),
        'SLDL': ('SLDL Rep Votes', 'SLDL Dem Votes'),
        }
    
    first_totals = upload.districts[0]['totals']

    for (prefix, (red_field, blue_field)) in gaps.items():
        if red_field not in first_totals or blue_field not in first_totals:
            continue
    
        red_districts = [d['totals'].get(red_field) or 0 for d in upload.districts]
        blue_districts = [d['totals'].get(blue_field) or 0 for d in upload.districts]

        if prefix == 'Red/Blue':
            summary_dict['Mean-Median'] = calculate_MMD(red_districts, blue_districts)
            summary_dict['Partisan Bias'] = calculate_PB(red_districts, blue_districts)
            summary_dict['Efficiency Gap'] = calculate_EG(red_districts, blue_districts)

            # Calculate -5 to +5 point swings
            swings = itertools.product([1, 2, 3, 4, 5], [(.01, 'Blue'), (-.01, 'Red')])
            for (points, (swing, party)) in swings:
                gap = calculate_EG(red_districts, blue_districts, swing * points)
                summary_dict[f'Efficiency Gap +{points:.0f} {party}'] = gap
        else:
            summary_dict[f'{prefix} Mean-Median'] = calculate_MMD(red_districts, blue_districts)
            summary_dict[f'{prefix} Partisan Bias'] = calculate_PB(red_districts, blue_districts)
            summary_dict[f'{prefix} Efficiency Gap'] = calculate_EG(red_districts, blue_districts)

            # Calculate -5 to +5 point swings
            swings = itertools.product([1, 2, 3, 4, 5], [(.01, 'Dem'), (-.01, 'Rep')])
            for (points, (swing, party)) in swings:
                gap = calculate_EG(red_districts, blue_districts, swing * points)
                summary_dict[f'{prefix} Efficiency Gap +{points:.0f} {party}'] = gap
    
    return upload.clone(summary=summary_dict)

def calculate_open_biases(upload):
    ''' Calculate partisan metrics for districts with multiple simulations.

        Look for "DEM000"-style vote properties from 2018 and 2019 PlanScore models.
    '''
    if f'DEM000' not in upload.districts[0]['totals']:
        # Skip everything if we don't see a "DEM000"-style vote property
        return upload.clone()
    
    MMDs, PBs = list(), list()
    EGs = {swing: list() for swing in (0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5)}
    summary_dict, copied_districts = dict(), copy.deepcopy(upload.districts)
    first_totals = copied_districts[0]['totals']
    
    # Prepare place for simulation vote totals in each district
    all_red_districts = [list() for d in copied_districts]
    all_blue_districts = [list() for d in copied_districts]

    # Iterate over all simulations, tracking EG and vote totals
    for sim in range(1000):
        if f'REP{sim:03d}' not in first_totals or f'DEM{sim:03d}' not in first_totals:
            continue
        
        sim_red_districts, sim_blue_districts = list(), list()

        for (i, district) in enumerate(copied_districts):
            red_votes = district['totals'].pop(f'REP{sim:03d}', 0)
            blue_votes = district['totals'].pop(f'DEM{sim:03d}', 0)
            sim_red_districts.append(red_votes)
            sim_blue_districts.append(blue_votes)
            all_red_districts[i].append(red_votes)
            all_blue_districts[i].append(blue_votes)
    
        MMDs.append(calculate_MMD(sim_red_districts, sim_blue_districts))
        PBs.append(calculate_PB(sim_red_districts, sim_blue_districts))
        
        for swing in EGs:
            EGs[swing].append(calculate_EG(sim_red_districts, sim_blue_districts, swing/100))
    
    # Finalize per-district vote totals and confidence intervals
    for (i, district) in enumerate(copied_districts):
        red_votes, blue_votes = all_red_districts[i], all_blue_districts[i]
        district['totals'].update({
            'Democratic Votes': round(statistics.mean(blue_votes), constants.ROUND_COUNT),
            'Republican Votes': round(statistics.mean(red_votes), constants.ROUND_COUNT),
            'Democratic Votes SD': round(statistics.stdev(blue_votes), constants.ROUND_COUNT),
            'Republican Votes SD': round(statistics.stdev(red_votes), constants.ROUND_COUNT)
            })

    summary_dict['Mean-Median'] = statistics.mean(MMDs)
    summary_dict['Mean-Median SD'] = statistics.stdev(MMDs)
    summary_dict['Partisan Bias'] = statistics.mean(PBs)
    summary_dict['Partisan Bias SD'] = statistics.stdev(PBs)
    summary_dict['Efficiency Gap'] = statistics.mean(EGs[0])
    summary_dict['Efficiency Gap SD'] = statistics.stdev(EGs[0])
    
    for swing in (1, 2, 3, 4, 5):
        summary_dict[f'Efficiency Gap +{swing} Dem'] = statistics.mean(EGs[swing])
        summary_dict[f'Efficiency Gap +{swing} Rep'] = statistics.mean(EGs[-swing])
        summary_dict[f'Efficiency Gap +{swing} Dem SD'] = statistics.stdev(EGs[swing])
        summary_dict[f'Efficiency Gap +{swing} Rep SD'] = statistics.stdev(EGs[-swing])
    
    rounded_summary_dict = {k: round(v, constants.ROUND_FLOAT) for (k, v) in summary_dict.items()}
    return upload.clone(districts=copied_districts, summary=rounded_summary_dict)

def calculate_biases(upload):
    ''' Calculate partisan metrics for districts with simulations and incumbency.
    
        Look for "O:DEM000"-style vote properties from PlanScore models starting 2020.
    '''
    if FIELD_TMPL.format(party='DEM', sim=0, incumbent=data.Incumbency.Open.value) \
            not in upload.districts[0]['totals']:
        # Skip everything if we don't see an "O:DEM000"-style vote property
        return upload.clone()
    
    MMDs, PBs = list(), list()
    EGs = {swing: list() for swing in (0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5)}
    summary_dict, copied_districts = dict(), copy.deepcopy(upload.districts)
    first_totals = copied_districts[0]['totals']
    
    # Prepare place for simulation vote totals in each district
    all_red_districts = [list() for d in copied_districts]
    all_blue_districts = [list() for d in copied_districts]

    # Iterate over all simulations, tracking EG and vote totals
    for sim in range(1000):
        if FIELD_TMPL.format(party='DEM', sim=sim, incumbent=data.Incumbency.Open.value) \
                not in first_totals:
            # Skip if we don't seem to have sims up to this iteration
            continue
        
        sim_red_districts, sim_blue_districts = list(), list()

        for (i, district) in enumerate(copied_districts):
            incumbent = upload.incumbents[i]
            oDEMnnn = FIELD_TMPL.format(party='DEM', sim=sim, incumbent=incumbent)
            oREPnnn = FIELD_TMPL.format(party='REP', sim=sim, incumbent=incumbent)
        
            red_votes = district['totals'].pop(oREPnnn, 0)
            blue_votes = district['totals'].pop(oDEMnnn, 0)
            sim_red_districts.append(red_votes)
            sim_blue_districts.append(blue_votes)
            all_red_districts[i].append(red_votes)
            all_blue_districts[i].append(blue_votes)
            
            # Clear out vote total fields for all conditions in the current sim
            for (party, incumbent) in itertools.product(('DEM', 'REP'), list(data.Incumbency)):
                kwargs = dict(incumbent=incumbent.value, party=party, sim=sim)
                district['totals'].pop(FIELD_TMPL.format(**kwargs), None)
    
        MMDs.append(calculate_MMD(sim_red_districts, sim_blue_districts))
        PBs.append(calculate_PB(sim_red_districts, sim_blue_districts))
        
        for swing in EGs:
            EGs[swing].append(calculate_EG(sim_red_districts, sim_blue_districts, swing/100))
    
    # Finalize per-district vote totals and confidence intervals
    for (i, district) in enumerate(copied_districts):
        red_votes, blue_votes = all_red_districts[i], all_blue_districts[i]
        district['totals'].update({
            'Democratic Votes': round(statistics.mean(blue_votes), constants.ROUND_COUNT),
            'Republican Votes': round(statistics.mean(red_votes), constants.ROUND_COUNT),
            'Democratic Votes SD': round(statistics.stdev(blue_votes), constants.ROUND_COUNT),
            'Republican Votes SD': round(statistics.stdev(red_votes), constants.ROUND_COUNT)
            })

    summary_dict['Mean-Median'] = statistics.mean(MMDs)
    summary_dict['Mean-Median SD'] = statistics.stdev(MMDs)
    summary_dict['Partisan Bias'] = statistics.mean(PBs)
    summary_dict['Partisan Bias SD'] = statistics.stdev(PBs)
    summary_dict['Efficiency Gap'] = statistics.mean(EGs[0])
    summary_dict['Efficiency Gap SD'] = statistics.stdev(EGs[0])
    
    for swing in (1, 2, 3, 4, 5):
        summary_dict[f'Efficiency Gap +{swing} Dem'] = statistics.mean(EGs[swing])
        summary_dict[f'Efficiency Gap +{swing} Rep'] = statistics.mean(EGs[-swing])
        summary_dict[f'Efficiency Gap +{swing} Dem SD'] = statistics.stdev(EGs[swing])
        summary_dict[f'Efficiency Gap +{swing} Rep SD'] = statistics.stdev(EGs[-swing])
    
    rounded_summary_dict = {k: round(v, constants.ROUND_FLOAT) for (k, v) in summary_dict.items()}
    return upload.clone(districts=copied_districts, summary=rounded_summary_dict)

def calculate_district_biases(upload):
    ''' Calculate partisan metrics using district matrix with presidential vote only.
    
        Look for 2016 presidential vote totals to use national PlanScore model.
    '''
    ## TODO: remove print output unless running planscore-score-locally
    #
    #with open('EGs.csv', 'w') as file:
    #    print('wasted_red,wasted_blue', file=file)
    #
    #with open('MMDs.csv', 'w') as file:
    #    print('mean,median', file=file)
    #
    #with open('PBs.csv', 'w') as file:
    #    print('blue_seatshare,blue_voteshare', file=file)
    
    has_president_votes = (
        (
            'US President 2016 - DEM' in upload.districts[0]['totals']
            and 'US President 2016 - REP' in upload.districts[0]['totals']
        ) or (
            'US President 2020 - DEM' in upload.districts[0]['totals']
            and 'US President 2020 - REP' in upload.districts[0]['totals']
        )
    )
    
    if not has_president_votes:
        # Skip everything if we don't see 2016 presidential votes
        return upload.clone()
    
    # Get large number of simulated outputs
    output_votes = matrix.model_votes(
        upload.model.state,
        matrix.YEAR,
        matrix.prepare_district_data(upload),
    )
    
    # Record per-district vote totals and confidence intervals
    copied_districts = copy.deepcopy(upload.districts)
    
    for (i, district) in enumerate(copied_districts):
        red_votes = matrix.dropna(output_votes[i,:,1])
        blue_votes = matrix.dropna(output_votes[i,:,0])
        try:
            district['totals'].update({
                'Democratic Wins': (blue_votes > red_votes).astype(int).sum() / output_votes.shape[1],
                'Democratic Votes': round(statistics.mean(blue_votes), constants.ROUND_COUNT),
                'Republican Votes': round(statistics.mean(red_votes), constants.ROUND_COUNT),
                'Democratic Votes SD': round(statistics.stdev(blue_votes), constants.ROUND_COUNT),
                'Republican Votes SD': round(statistics.stdev(red_votes), constants.ROUND_COUNT)
                })
        except statistics.StatisticsError:
            district['totals'].update({
                'Democratic Wins': None,
                'Democratic Votes': None,
                'Republican Votes': None,
                'Democratic Votes SD': None,
                'Republican Votes SD': None,
                })
    
    # For each sim, a list of red votes and a list of blue votes in districts
    red_votes_blue_votes = [
        (
            matrix.dropna(output_votes[:,sim,1]).tolist(),
            matrix.dropna(output_votes[:,sim,0]).tolist(),
        )
        for sim in range(output_votes.shape[1])
    ]
    
    # Calculate partisanship metrics for all simulations
    MMDs = [calculate_MMD(r, b) for (r, b) in red_votes_blue_votes]
    PBs = [calculate_PB(r, b) for (r, b) in red_votes_blue_votes]
    
    # EG alone also gets a sensitivity test for vote swing scenarios
    EGs = {
        swing: [calculate_EG(r, b, swing/100) for (r, b) in red_votes_blue_votes]
        for swing in (0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5)
    }

    summary_dict = {
        'Mean-Median': statistics.mean(MMDs),
        'Mean-Median SD': statistics.stdev(MMDs),
        'Mean-Median Positives': len([n for n in MMDs if n > 0]) / len(MMDs),
        'Partisan Bias': statistics.mean(PBs),
        'Partisan Bias SD': statistics.stdev(PBs),
        'Partisan Bias Positives': len([n for n in PBs if n > 0]) / len(PBs),
        'Efficiency Gap': statistics.mean(EGs[0]),
        'Efficiency Gap SD': statistics.stdev(EGs[0]),
        'Efficiency Gap Positives': len([n for n in EGs[0] if n > 0]) / len(EGs[0]),
    }
    
    for swing in (1, 2, 3, 4, 5):
        summary_dict.update({
            f'Efficiency Gap +{swing} Dem': statistics.mean(EGs[swing]),
            f'Efficiency Gap +{swing} Rep': statistics.mean(EGs[-swing]),
            f'Efficiency Gap +{swing} Dem SD': statistics.stdev(EGs[swing]),
            f'Efficiency Gap +{swing} Rep SD': statistics.stdev(EGs[-swing]),
        })

    rounded_summary_dict = {k: round(v, constants.ROUND_FLOAT) for (k, v) in summary_dict.items()}
    return upload.clone(districts=copied_districts, summary=rounded_summary_dict)

parser = argparse.ArgumentParser()
parser.add_argument('upload_url')

def main():
    ''' Write all district vote simulations to single CSV file
    '''
    args = parser.parse_args()

    got = urllib.request.urlopen(args.upload_url)
    upload1 = data.Upload.from_json(got.read())

    upload2 = calculate_bias(upload1)
    upload3 = calculate_open_biases(upload2)
    upload4 = calculate_biases(upload3)
    upload5 = calculate_district_biases(upload4)

    complete_upload = upload5.clone(message='Finished scoring this plan.')
    
    print('''Scores for {id} ({state}, {house}):
EG: {EG:.1f}%; {EG_wins:.0f}% favor D
GK Bias: {PB:.1f}%; {PB_wins:.0f}% favor D
Mean-Med: {MMD:.1f}%; {MMD_wins:.0f}% favor D
-
D votes: {votes_D}
R votes: {votes_R}'''.format(
        id=complete_upload.id,
        state=complete_upload.model.state,
        house=complete_upload.model.house,
        EG=complete_upload.summary['Efficiency Gap'] * 100,
        EG_wins=complete_upload.summary['Efficiency Gap Positives'] * 100,
        PB=complete_upload.summary['Partisan Bias'] * 100,
        PB_wins=complete_upload.summary['Partisan Bias Positives'] * 100,
        MMD=complete_upload.summary['Mean-Median'] * 100,
        MMD_wins=complete_upload.summary['Mean-Median Positives'] * 100,
        votes_D=[round(d['totals']['Democratic Votes'], 1) for d in complete_upload.districts],
        votes_R=[round(d['totals']['Republican Votes'], 1) for d in complete_upload.districts],
    ))
