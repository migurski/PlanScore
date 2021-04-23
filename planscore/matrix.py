import os
import csv
import gzip
import itertools
import collections
import argparse
import urllib.request

import numpy

from . import data

# The presidential vote in the model is mean-deviated, so you have to subtract
# this adjustment value from the presidential vote values in each district.
# Values are given as Democratic vote portion from 0. to 1. and become
# approximately -0.5 to +0.5.
VOTE_ADJUST = -0.496875

# A hard-coded year to use for matrix, nothing for now
YEAR = None

INCUMBENCY = {
    data.Incumbency.Open.value: 0,
    data.Incumbency.Democrat.value: 1,
    data.Incumbency.Republican.value: -1,
}

STATE = {
    data.State.XX: 'ks', # Null Ranch
    
    data.State.AR: 'ar',
    data.State.AZ: 'az',
    data.State.CA: 'ca',
    data.State.CO: 'co',
    data.State.FL: 'fl',
    data.State.GA: 'ga',
    data.State.IA: 'ia',
    data.State.IL: 'il',
    data.State.IN: 'in',
    data.State.KS: 'ks',
    data.State.KY: 'ky',
    data.State.LA: 'la',
    data.State.MA: 'ma',
    data.State.MD: 'md',
    data.State.MI: 'mi',
    data.State.MN: 'mn',
    data.State.MO: 'mo',
    data.State.NC: 'nc',
    data.State.NJ: 'nj',
    data.State.NV: 'nv',
    data.State.OH: 'oh',
    data.State.OK: 'ok',
    data.State.OR: 'or',
    data.State.PA: 'pa',
    data.State.SC: 'sc',
    data.State.TN: 'tn',
    data.State.TX: 'tx',
    data.State.VA: 'va',
    data.State.WA: 'wa',
    data.State.WI: 'wi',
}

Model = collections.namedtuple('Model', (
    'intercept', 'vote', 'incumbent',
    'state_intercept', 'state_vote', 'state_incumbent',
    #'year_intercept', 'year_vote', 'year_incumbent',
    'c_matrix', 'e_matrix',
    ))

def dropna(a):
    return a[~numpy.isnan(a)]

def load_model(state, year):
    assert year is None, f'Year should be None, not {year}'

    matrix_dir = os.path.join(os.path.dirname(__file__), 'model')
    c_path = os.path.join(matrix_dir, 'C_matrix_full.csv.gz')
    e_path = os.path.join(matrix_dir, 'E_matrix_full.csv.gz')
    
    c_keys = (
        'b_Intercept', 'b_dpres_mn', 'b_incumb',
        f'r_stateabrev[{state},Intercept]',
        f'r_stateabrev[{state},dpres_mn]',
        f'r_stateabrev[{state},incumb]',
        #f'r_cycle[{year},Intercept]',
        #f'r_cycle[{year},dpres_mn]',
        #f'r_cycle[{year},incumb]',
    )
    
    with gzip.open(c_path, 'rt') as c_file:
        c_rows = {
            c_row['']: [
                float(c_value)
                for (c_col, c_value) in c_row.items()
                if c_col.startswith('V')
            ]
            for c_row in csv.DictReader(c_file)
            if c_row[''] in c_keys
        }
    
    with gzip.open(e_path, 'rt') as e_file:
        e_rows = [
            [
                float(e_value)
                for (e_col, e_value) in e_row.items()
                if e_col.startswith('V')
            ]
            for e_row in csv.DictReader(e_file)
        ]
    
    c_values = [c_rows[c_key] for c_key in c_keys]
    args = c_values + [numpy.array(c_values), numpy.array(e_rows)]
    
    return Model(*args)

def apply_model(districts, model):
    ''' districts is an array of two-element tuples:
        - Democratic vote portion from 0. to 1.
        - -1 for Republican, 0 for open seat, and 1 for Democratic incumbents
    '''
    AD = numpy.array([
        [1, numpy.nan if numpy.isnan(vote) else (vote + VOTE_ADJUST), incumbency] * 2
        for (vote, incumbency)
        in districts
    ])
    
    ## TODO: remove print output unless running planscore-score-locally
    #
    #print('AD:', AD.shape)
    #numpy.savetxt('AD.csv', AD, fmt='%.9f', delimiter=',')
    
    ADC = AD.dot(model.c_matrix)
    #print('ADC:', ADC.shape)
    #numpy.savetxt('ADC.csv', ADC, fmt='%.9f', delimiter=',')
    #print('C:', model.c_matrix.shape)
    #numpy.savetxt('C.csv', model.c_matrix, fmt='%.9f', delimiter=',')
    E = model.e_matrix[:len(districts),:]
    #print('E:', E.shape)
    #numpy.savetxt('E.csv', E, fmt='%.9f', delimiter=',')

    #print('ADCE:', (ADC + E).shape)
    #numpy.savetxt('ADCE.csv', (ADC + E), fmt='%.9f', delimiter=',')
    return ADC + E

def model_votes(state, year, districts):
    ''' Convert presidential votes to range of possible modeled chamber votes.
        
        state is from data.State enum, year is an integer.
        districts is an array of three-element tuples:
        - Input Democratic vote count
        - Input Republican vote count
        - Incumbency: "O" for open, "R", or "D"
        
        Return is a DxSx2 matrix for D districts, S simulations, and Dem/Rep parties.
    '''
    # Get DxS array from apply_model() with modeled vote fractions
    fractions = apply_model(
        [
            (dem / ((dem + rep) or numpy.nan), INCUMBENCY[inc])
            for (dem, rep, inc) in districts
        ],
        load_model(STATE[state], year),
    )
    
    # Make DxS array with total vote counts for each district and simulation
    total_votes = sum([dem + rep for (dem, rep, _) in districts])
    one_district_votes = total_votes / len(districts)
    per_district_votes = [[one_district_votes]] * len(districts)
    #per_district_votes = [[dem + rep] for (dem, rep, _) in districts]
    
    scale = numpy.repeat(per_district_votes, fractions.shape[1], axis=1)
    
    # Build DxSx2 array with per-party vote totals for each district and simulation
    votes_dem = (fractions * scale).round(1)
    votes_rep = ((1 - fractions) * scale).round(1)
    votes = numpy.concatenate(
        (numpy.expand_dims(votes_dem, 2), numpy.expand_dims(votes_rep, 2)),
        axis=2,
    )
    
    return votes

def prepare_district_data(upload):
    ''' Simple presidential vote input for model_votes()
    '''
    data = []
    
    for (district, incumbency) in zip(upload.districts, upload.incumbents):
        if 'US President 2016 - DEM' in district['totals']:
            data.append((
                district['totals']['US President 2016 - DEM'],
                district['totals']['US President 2016 - REP'],
                incumbency,
            ))
        else:
            total = district['totals']['US President 2020 - DEM'] \
                  + district['totals']['US President 2020 - REP']
            pvote_2020 = district['totals']['US President 2020 - DEM'] / total
            pvote_2016 = 1.07 * pvote_2020 - 4.6e-2

            data.append((
                total * pvote_2016,
                total * (1 - pvote_2016),
                incumbency,
            ))
    
    return data

parser = argparse.ArgumentParser()
parser.add_argument('upload_url')
parser.add_argument('matrix_path')

def main():
    ''' Write all district vote simulations to single CSV file
    '''
    args = parser.parse_args()

    got = urllib.request.urlopen(args.upload_url)
    upload = data.Upload.from_json(got.read())
    input_district_data = prepare_district_data(upload)
    
    # Get large number of simulated outputs
    output_votes = model_votes(upload.model.state, YEAR, input_district_data)

    with open(args.matrix_path, 'w') as file:
        districts, sims, parties = output_votes.shape
        votes_matrix = output_votes.reshape((districts, sims * parties))
    
        out = csv.writer(file, dialect='excel')
        head = itertools.chain(*[[f'DEM{n:03d}', f'REP{n:03d}'] for n in range(sims)])
        out.writerow(['District'] + list(head))
        for (index, row) in enumerate(votes_matrix.tolist()):
            out.writerow([index + 1] + row)
