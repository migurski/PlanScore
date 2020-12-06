import os
import csv
import collections

import numpy

from . import data

# The presidential vote in the model is mean-deviated, so you have to subtract
# this adjustment value from the presidential vote values in each district.
# Values are given as Democratic vote portion from 0. to 1. and become
# approximately -0.5 to +0.5.
VOTE_ADJUST = -0.496875

INCUMBENCY = {
    data.Incumbency.Open.value: 0,
    data.Incumbency.Democrat.value: 1,
    data.Incumbency.Republican.value: -1,
}

STATE = {
    data.State.XX: 'ks', # Null Ranch
    
    data.State.MD: 'md',
    data.State.NC: 'nc',
    data.State.PA: 'pa',
    data.State.VA: 'va',
    data.State.WI: 'wi',
    data.State.FL: 'fl',
    data.State.TX: 'tx',
    data.State.GA: 'ga',
    data.State.IL: 'il',
    data.State.MA: 'ma',
    data.State.MI: 'mi',
    data.State.TN: 'tn',
    data.State.DE: 'de',
    data.State.ME: 'me',
    data.State.MT: 'mt',
    data.State.ND: 'nd',
    data.State.NH: 'nh',
    data.State.RI: 'ri',
    data.State.SD: 'sd',
    data.State.VT: 'vt',
    data.State.WY: 'wy',
}

Model = collections.namedtuple('Model', (
    'intercept', 'vote', 'incumbent',
    'state_intercept', 'state_vote', 'state_incumbent',
    'year_intercept', 'year_vote', 'year_incumbent',
    'array',
    ))

def dropna(a):
    return a[~numpy.isnan(a)]

def load_model(state, year):
    path = os.path.join(os.path.dirname(__file__), 'model', 'C_matrix.csv')
    
    keys = (
        'Intercept', 'dpres_mn', 'incumb',
        f'{state}-Intercept', f'{state}-dpres', f'{state}-incumb',
        f'{year}-Intercept', f'{year}-dpres', f'{year}-incumb',
    )
    
    with open(path) as file:
        rows = {
            row['']: [
                float(value)
                for (key, value) in row.items()
                if key.startswith('V')
            ]
            for row in csv.DictReader(file)
            if row[''] in keys
        }
    
    values = [rows[key] for key in keys]
    args = values + [numpy.array(values)]
    
    return Model(*args)

def apply_model(districts, model):
    ''' districts is an array of two-element tuples:
        - Democratic vote portion from 0. to 1.
        - -1 for Republican, 0 for open seat, and 1 for Democratic incumbents
    '''
    AD = numpy.array([
        [1, numpy.nan if numpy.isnan(vote) else (vote + VOTE_ADJUST), incumbency] * 3
        for (vote, incumbency)
        in districts
    ])

    return AD.dot(model.array)

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
    scale = numpy.repeat(
        [[dem + rep] for (dem, rep, _) in districts],
        fractions.shape[1],
        axis=1,
        )
    
    # Build DxSx2 array with per-party vote totals for each district and simulation
    votes_dem = (fractions * scale).round(1)
    votes_rep = ((1 - fractions) * scale).round(1)
    votes = numpy.concatenate(
        (numpy.expand_dims(votes_dem, 2), numpy.expand_dims(votes_rep, 2)),
        axis=2,
    )
    
    return votes
