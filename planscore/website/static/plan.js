var FIELDS = [
    'Population 2010',
    'Population 2015',
    'Black Population 2015',
    'Hispanic Population 2015',
    'Population 2016',
    'Black Population 2016',
    'Hispanic Population 2016',
    'Population 2018',
    'Black Population 2018',
    'Hispanic Population 2018',
    'Population 2019',
    'Black Population 2019',
    'Hispanic Population 2019',
    'Citizen Voting-Age Population 2015',
    'Black Citizen Voting-Age Population 2015',
    'Hispanic Citizen Voting-Age Population 2015',
    'Citizen Voting-Age Population 2018',
    'Black Citizen Voting-Age Population 2018',
    'Hispanic Citizen Voting-Age Population 2018',
    'Citizen Voting-Age Population 2019',
    'Black Citizen Voting-Age Population 2019',
    'Hispanic Citizen Voting-Age Population 2019',
    'Democratic Wins',
    'Democratic Votes',
    'Republican Votes',
    'US President 2016 - DEM',
    'US President 2016 - REP',
    'US President 2020 - DEM',
    'US President 2020 - REP'
    /*, 'Polsby-Popper', 'Reock'*/
];

var BLUE_COLOR_HEX = '#4D90D1',
    RED_COLOR_HEX = '#D45557',
    LEAN_BLUE_COLOR_HEX = '#6D8AB1',
    LEAN_RED_COLOR_HEX = '#B56E6B',
    BLUEISH_COLOR_HEX = '#6D8AB0',
    REDDISH_COLOR_HEX = '#B56E6A',
    UNKNOWN_COLOR_HEX = '#838383';

function format_url(url_pattern, id)
{
    return url_pattern.replace('{id}', id);
}

function nice_count(value)
{
    if(value >= 1000)
    {
        var raw = value.toFixed(0);
        
        while(raw.match(/\d\d\d\d\b/))
        {
            raw = raw.replace(/(\d)(\d\d\d)\b/, '$1,$2');
        }
        
        return raw;
    }
    
    if(value >= 100) {
        return value.toFixed(0);
    } else if(value >= 10) {
        return value.toFixed(1);
    } else if(value >= 0) {
        return value.toFixed(2);
    } else {
        return '–';
    }
}

function nice_percent(value)
{
    return (100 * value).toFixed(1) + '%';
}

function nice_round_percent(value)
{
    if(value < .01) {
        return '<1%';
    } else if(value > .99) {
        return '>99%';
    } else {
        return (100 * value).toFixed(0) + '%';
    }
}

function nice_gap(value)
{
    if(value > 0) {
        return '+' + nice_percent(value) + ' for Democrats';
    } else {
        return '+' + nice_percent(-value) + ' for Republicans';
    }
}

function nice_string(value)
{
    return value.replace(/./gm, function(c) { return "&#" + c.charCodeAt(0) + ";" });
}

function clear_element(el)
{
    while(el.lastChild)
    {
        el.removeChild(el.lastChild);
    }
}

function date_age(date)
{
    return (new Date()).getTime() / 1000 - date.getTime() / 1000;
}

function what_score_description_text(plan)
{
    if(typeof plan['description'] === 'string')
    {
        return plan['description'];
    }

    return false; // No description provided
}

function which_score_summary_name(plan)
{
    var summaries = [
        'US House Efficiency Gap', 'Efficiency Gap',
        'SLDL Efficiency Gap', 'SLDU Efficiency Gap'
        ];

    for(var i = 0; i < summaries.length; i++)
    {
        var name = summaries[i];

        if(typeof plan.summary[name] === 'number')
        {
            return name;
        }
    }

    return null;
}

function which_score_column_names(plan)
{
    if(typeof plan.summary['Efficiency Gap Positives'] === 'number'
    || typeof plan.summary['Efficiency Gap SD'] === 'number')
    {
        return FIELDS.slice();
    }

    if(typeof plan.summary['US House Efficiency Gap'] === 'number')
    {
        return [
            'Population', 'Voting-Age Population', 'Black Voting-Age Population',
            'US House Dem Votes', 'US House Rep Votes'
        ];
    }

    if(typeof plan.summary['Efficiency Gap'] === 'number')
    {
        return ['Voters', 'Blue Votes', 'Red Votes'];
    }

    return [];
}

function which_district_color(district, plan)
{
    // Colors from http://chromatron.s3-website-us-east-1.amazonaws.com/#eNpVz8EKgzAQBNB/mV5z2JhsYvIrpQc1tkilgqXQIv57NYkNZa77mNkF3TRO8xP+vGAI8CRwHcYRHicdHAUJgTe8dizwgZdWCszwNa0iAVlA0MxsE6ikSsC4CCT9RFVErfYkodjlCopCmwOoAlo2vWkyIPUHTHUAXYAJddNSfkLavMlGwG69CLRNd7/N0+sR4iLas90Pj9Bvhtcv8ANJtQ==

    var totals = district.totals;
    
    if(typeof totals['Democratic Wins'] === 'number')
    {
        if(totals['Democratic Wins'] > .75) {
            return BLUE_COLOR_HEX;
        } else if (totals['Democratic Wins'] < .25) {
            return RED_COLOR_HEX;
        } else if (totals['Democratic Wins'] > .5) {
            return LEAN_BLUE_COLOR_HEX;
        } else if (totals['Democratic Wins'] < .5) {
            return LEAN_RED_COLOR_HEX;
        } else {
            return UNKNOWN_COLOR_HEX;
        }
    }

    if(typeof plan.summary['Efficiency Gap Positives'] === 'number'
    || typeof plan.summary['Efficiency Gap SD'] === 'number')
    {
        var dem_votes = totals['Democratic Votes'],
            rep_votes = totals['Republican Votes'],
            dem_votes_sd = totals['Democratic Votes SD'],
            rep_votes_sd = totals['Republican Votes SD'];
    
        if((dem_votes - dem_votes_sd*2) > (rep_votes + rep_votes_sd*2)) {
            return BLUE_COLOR_HEX;
        } else if((dem_votes + dem_votes_sd*2) < (rep_votes - rep_votes_sd*2)) {
            return RED_COLOR_HEX;
        } else if((dem_votes - dem_votes_sd) > (rep_votes + rep_votes_sd)) {
            return BLUEISH_COLOR_HEX;
        } else if((dem_votes + dem_votes_sd) < (rep_votes - rep_votes_sd)) {
            return REDDISH_COLOR_HEX;
        } else {
            return UNKNOWN_COLOR_HEX;
        }
    }

    if(typeof plan.summary['US House Efficiency Gap'] === 'number')
    {
        if(totals['US House Dem Votes'] > totals['US House Rep Votes']) {
            return BLUE_COLOR_HEX;
        } else {
            return RED_COLOR_HEX;
        }
    }

    if(typeof plan.summary['Efficiency Gap'] === 'number')
    {
        if(totals['Blue Votes'] > totals['Red Votes']) {
            return BLUE_COLOR_HEX;
        } else {
            return RED_COLOR_HEX;
        }
    }

    // neutral gray
    return '#808080';
}

function show_efficiency_gap_score(plan, score_EG)
{
    var summary_name = which_score_summary_name(plan),
        gap = plan.summary[summary_name],
        gap_amount = nice_percent(Math.abs(gap));
    
    for(node = score_EG.firstChild; node = node.nextSibling; node)
    {
        if(node.nodeName == 'H3') {
            node.innerHTML += ': ' + gap_amount;

        } else if(node.nodeName == 'DIV') {
            drawBiasBellChart('eg', gap, node.id,
                (plan.model ? plan.model.house : 'ushouse'), 'plan');

        } else if(node.nodeName == 'P') {
            var win_party = (gap < 0 ? 'Republican' : 'Democratic'),
                win_partisans = (gap < 0 ? 'Republicans' : 'Democrats'),
                lose_party = (gap < 0 ? 'Democratic' : 'Republican');

            clear_element(node);
            
            if(typeof plan.summary['Efficiency Gap Positives'] === 'number') {
                var positives = (gap < 0
                    ? (1 - plan.summary['Efficiency Gap Positives'])
                    : plan.summary['Efficiency Gap Positives']);
            
                node.innerHTML = [
                    'Votes for', win_party, 'candidates are expected to be wasted at a rate',
                    gap_amount, 'lower than votes for', lose_party, 'candidates.',
                    'The expected gap favors', win_partisans,
                    'in', nice_round_percent(positives), 'of predicted scenarios.',
                    '<a href="' + window.eg_metric_url + '">Learn more <i class="glyphicon glyphicon-chevron-right" style="font-size:0.8em;"></i></a>'
                    ].join(' ');

            } else {
                var gap_error = plan.summary['Efficiency Gap SD'];
                
                node.innerHTML = [
                    'Votes for', win_party, 'candidates are expected to be wasted at a rate',
                    gap_amount+'&nbsp;(±'+nice_percent(gap_error*2)+')',
                    'lower than votes for', lose_party, 'candidates.',
                    '<a href="' + window.eg_metric_url + '">Learn more <i class="glyphicon glyphicon-chevron-right" style="font-size:0.8em;"></i></a>'
                    ].join(' ');
            }
        }
    }
}

function show_partisan_bias_score(plan, score_PB)
{
    var bias = plan.summary['Partisan Bias'],
        bias_amount = nice_percent(Math.abs(bias));
    
    for(node = score_PB.firstChild; node = node.nextSibling; node)
    {
        if(node.nodeName == 'H3') {
            node.innerHTML += ': ' + bias_amount;

        } else if(node.nodeName == 'DIV') {
            drawBiasBellChart('pb', bias, node.id,
                (plan.model ? plan.model.house : 'ushouse'), 'plan');

        } else if(node.nodeName == 'P') {
            var win_party = (bias < 0 ? 'Republicans' : 'Democrats'),
                win_partisans = (bias < 0 ? 'Republicans' : 'Democrats');

            clear_element(node);
            
            if(typeof plan.summary['Partisan Bias Positives'] === 'number') {
                var positives = (bias < 0
                    ? (1 - plan.summary['Partisan Bias Positives'])
                    : plan.summary['Partisan Bias Positives']);
            
                node.innerHTML = [
                    win_party, 'would be expected to win', bias_amount,
                    'extra seats in a hypothetical, perfectly tied election.',
                    'The expected bias favors', win_partisans,
                    'in', nice_round_percent(positives), 'of predicted scenarios.',
                    '<a href="' + window.pb_metric_url + '">Learn more <i class="glyphicon glyphicon-chevron-right" style="font-size:0.8em;"></i></a>'
                    ].join(' ');

            } else {
                var bias_error = plan.summary['Partisan Bias SD'];
                
                node.innerHTML = [
                    win_party, 'would be expected to win',
                    bias_amount+'&nbsp;(±'+nice_percent(bias_error*2)+')',
                    'extra seats in a hypothetical, perfectly tied election.',
                    '<a href="' + window.pb_metric_url + '">Learn more <i class="glyphicon glyphicon-chevron-right" style="font-size:0.8em;"></i></a>'
                    ].join(' ');
            }
        }
    }
}

function hide_score_with_reason(score_node, reason)
{
    for(node = score_node.firstChild; node = node.nextSibling; node)
    {
        if(node.nodeName == 'DIV')
        {
            clear_element(node);

        } else if(node.nodeName == 'P') {
            clear_element(node);
            node.appendChild(document.createTextNode(reason));
        }
    }
}

function show_mean_median_score(plan, score_MM)
{
    var diff = plan.summary['Mean-Median'],
        diff_amount = nice_percent(Math.abs(diff));
    
    for(node = score_MM.firstChild; node = node.nextSibling; node)
    {
        if(node.nodeName == 'H3') {
            node.innerHTML += ': ' + diff_amount;

        } else if(node.nodeName == 'DIV') {
            drawBiasBellChart('mm', diff, node.id,
                (plan.model ? plan.model.house : 'ushouse'), 'plan');

        } else if(node.nodeName == 'P') {
            var win_party = (diff < 0 ? 'Republican' : 'Democrat'),
                win_partisans = (diff < 0 ? 'Republicans' : 'Democrats');

            clear_element(node);
            
            if(typeof plan.summary['Mean-Median Positives'] === 'number') {
                var positives = (diff < 0
                    ? (1 - plan.summary['Mean-Median Positives'])
                    : plan.summary['Mean-Median Positives']);
            
                node.innerHTML = [
                    'The median', win_party, 'vote share is expected to be',
                    diff_amount, 'higher than the mean', win_party, 'vote share.',
                    'The expected difference favors', win_partisans,
                    'in', nice_round_percent(positives), 'of predicted scenarios.',
                    '<a href="' + window.mm_metric_url + '">Learn more <i class="glyphicon glyphicon-chevron-right" style="font-size:0.8em;"></i></a>'
                    ].join(' ');

            } else {
                var diff_error = plan.summary['Mean-Median SD'];
                
                node.innerHTML = [
                    'The median', win_party, 'vote share is expected to be',
                    diff_amount+'&nbsp;(±'+nice_percent(diff_error*2)+')',
                    'higher than the mean', win_party, 'vote share.',
                    '<a href="' + window.mm_metric_url + '">Learn more <i class="glyphicon glyphicon-chevron-right" style="font-size:0.8em;"></i></a>'
                    ].join(' ');
            }
        }
    }
}

function show_sensitivity_test(plan, score_sense)
{
    Highcharts.chart(score_sense, {
        chart: { type: 'line' },
        legend: { enabled: false },
        credits: { enabled: false },
        title: { text: null },
        series: [{
            name: 'Expected Efficiency Gap',
            data: [
                100 * plan.summary['Efficiency Gap +5 Dem'],
                100 * plan.summary['Efficiency Gap +4 Dem'],
                100 * plan.summary['Efficiency Gap +3 Dem'],
                100 * plan.summary['Efficiency Gap +2 Dem'],
                100 * plan.summary['Efficiency Gap +1 Dem'],
                100 * plan.summary['Efficiency Gap'],
                100 * plan.summary['Efficiency Gap +1 Rep'],
                100 * plan.summary['Efficiency Gap +2 Rep'],
                100 * plan.summary['Efficiency Gap +3 Rep'],
                100 * plan.summary['Efficiency Gap +4 Rep'],
                100 * plan.summary['Efficiency Gap +5 Rep']
                ]
        }],
        xAxis: {
            categories: ['+5 D', '+4 D', '+3 D', '+2 D', '+1 D', '0', '+1 R', '+2 R', '+3 R', '+4 R', '+5 R'],
            title: { text: 'Possible Vote Swing' }
        },
        yAxis: { title: { text: null } },
        plotOptions: {
            line: {
                dataLabels: { enabled: false },
                enableMouseTracking: false
            }
        }
    });
}

function show_message(text, score_section, message_section)
{
    while(message_section.firstChild)
    {
        message_section.removeChild(message_section.firstChild);
    }

    message_section.appendChild(document.createElement('p'));
    message_section.firstChild.appendChild(document.createTextNode(text));

    score_section.style.display = 'none';
    message_section.style.display = 'block';
}

function hide_message(score_section, message_section)
{
    score_section.style.display = 'block';
    message_section.style.display = 'none';
}

function update_heading_titles(head)
{
    var dem_index = head.indexOf('Democratic Votes'),
        rep_index = head.indexOf('Republican Votes'),
        wins_index = head.indexOf('Democratic Wins');

    if(wins_index >= 0)
    {
        head[wins_index] = 'Chance of Democratic Win';
        
        if(dem_index >= 0 && rep_index >= 0)
        {
            head[dem_index] = 'Predicted Vote Shares';
            head.splice(rep_index, 1);
        }
    } else if(dem_index >= 0 && rep_index >= 0) {
        head[dem_index] = 'Predicted Democratic Vote Share';
        head[rep_index] = 'Predicted Republican Vote Share';
    }

    if(head.indexOf('US President 2016 - DEM') >= 0 && head.indexOf('US President 2016 - REP') >= 0)
    {
        head[head.indexOf('US President 2016 - DEM')] = 'US President 2016: Clinton (D)';
        head[head.indexOf('US President 2016 - REP')] = 'US President 2016: Trump (R)';
    }

    if(head.indexOf('US President 2020 - DEM') >= 0 && head.indexOf('US President 2020 - REP') >= 0)
    {
        head[head.indexOf('US President 2020 - DEM')] = 'US President 2020: Biden (D)';
        head[head.indexOf('US President 2020 - REP')] = 'US President 2020: Trump (R)';
    }

    if(head.indexOf('Citizen Voting-Age Population 2015') >= 0
        && head.indexOf('Black Citizen Voting-Age Population 2015') >= 0
        && head.indexOf('Hispanic Citizen Voting-Age Population 2015') >= 0)
    {
        head[head.indexOf('Black Citizen Voting-Age Population 2015')] = 'Black Non-Hispanic CVAP 2015';
        head[head.indexOf('Hispanic Citizen Voting-Age Population 2015')] = 'Hispanic CVAP 2015';
    }
}

function update_vote_percentages(head, row, source_row)
{
    var dem_index = head.indexOf('Democratic Votes'),
        rep_index = head.indexOf('Republican Votes'),
        wins_index = head.indexOf('Democratic Wins'),
        vote_count;
    
    if(wins_index >= 0)
    {
        row[wins_index] = nice_round_percent(row[wins_index]);

        if(dem_index >= 0 && rep_index >= 0)
        {
            vote_count = (row[dem_index] + row[rep_index]);
            row[dem_index] = [
                nice_round_percent(row[dem_index] / vote_count), ' D / ',
                nice_round_percent(row[rep_index] / vote_count), ' R'
            ].join('');
            row.splice(rep_index, 1);
        }
    } else if(dem_index >= 0 && rep_index >= 0) {
        vote_count = (row[dem_index] + row[rep_index]);
        row[dem_index] = nice_percent(row[dem_index] / vote_count);
        row[rep_index] = nice_percent(row[rep_index] / vote_count);

        if(typeof source_row['Democratic Votes SD'] === 'number'
        && typeof source_row['Republican Votes SD'] === 'number')
        {
            row[dem_index] += ' (±' + nice_percent(2 * source_row['Democratic Votes SD'] / vote_count) + ')';
            row[rep_index] += ' (±' + nice_percent(2 * source_row['Republican Votes SD'] / vote_count) + ')';
        }
    }
}

function update_acs2015_percentages(head, row)
{
    var total_index = head.indexOf('Population 2015'),
        black_index = head.indexOf('Black Population 2015'),
        latin_index = head.indexOf('Hispanic Population 2015');

    if(total_index >= 0 && black_index >= 0 && latin_index >= 0)
    {
        row[black_index] = nice_percent(row[black_index] / row[total_index]);
        row[latin_index] = nice_percent(row[latin_index] / row[total_index]);
    }
}

function update_acs2016_percentages(head, row)
{
    var total_index = head.indexOf('Population 2016'),
        black_index = head.indexOf('Black Population 2016'),
        latin_index = head.indexOf('Hispanic Population 2016');

    if(total_index >= 0 && black_index >= 0 && latin_index >= 0)
    {
        row[black_index] = nice_percent(row[black_index] / row[total_index]);
        row[latin_index] = nice_percent(row[latin_index] / row[total_index]);
    }
}

function update_acs2018_percentages(head, row)
{
    var total_index = head.indexOf('Population 2018'),
        black_index = head.indexOf('Black Population 2018'),
        latin_index = head.indexOf('Hispanic Population 2018');

    if(total_index >= 0 && black_index >= 0 && latin_index >= 0)
    {
        row[black_index] = nice_percent(row[black_index] / row[total_index]);
        row[latin_index] = nice_percent(row[latin_index] / row[total_index]);
    }
}

function update_acs2019_percentages(head, row)
{
    var total_index = head.indexOf('Population 2019'),
        black_index = head.indexOf('Black Population 2019'),
        latin_index = head.indexOf('Hispanic Population 2019');

    if(total_index >= 0 && black_index >= 0 && latin_index >= 0)
    {
        row[black_index] = nice_percent(row[black_index] / row[total_index]);
        row[latin_index] = nice_percent(row[latin_index] / row[total_index]);
    }
}

function update_cvap2015_percentages(head, row)
{
    var total_index = head.indexOf('Citizen Voting-Age Population 2015'),
        black_index = head.indexOf('Black Citizen Voting-Age Population 2015'),
        latin_index = head.indexOf('Hispanic Citizen Voting-Age Population 2015');

    if(total_index >= 0 && black_index >= 0 && latin_index >= 0)
    {
        row[black_index] = nice_percent(row[black_index] / row[total_index]);
        row[latin_index] = nice_percent(row[latin_index] / row[total_index]);
    }
}

function update_cvap2018_percentages(head, row)
{
    var total_index = head.indexOf('Citizen Voting-Age Population 2018'),
        black_index = head.indexOf('Black Citizen Voting-Age Population 2018'),
        latin_index = head.indexOf('Hispanic Citizen Voting-Age Population 2018');

    if(total_index >= 0 && black_index >= 0 && latin_index >= 0)
    {
        row[black_index] = nice_percent(row[black_index] / row[total_index]);
        row[latin_index] = nice_percent(row[latin_index] / row[total_index]);
    }
}

function update_cvap2019_percentages(head, row)
{
    var total_index = head.indexOf('Citizen Voting-Age Population 2019'),
        black_index = head.indexOf('Black Citizen Voting-Age Population 2019'),
        latin_index = head.indexOf('Hispanic Citizen Voting-Age Population 2019');

    if(total_index >= 0 && black_index >= 0 && latin_index >= 0)
    {
        row[black_index] = nice_percent(row[black_index] / row[total_index]);
        row[latin_index] = nice_percent(row[latin_index] / row[total_index]);
    }
}

/*
 * Return a rows * columns matrix representing a scored plan table
 */
function plan_array(plan)
{
    var incumbency = {'O': 'Open Seat', 'D': 'Democratic Incumbent', 'R': 'Republican Incumbent'},
        has_incumbency = (plan.model && plan.model.incumbency 
            && plan.incumbents && plan.incumbents.length == plan.districts.length),
        fields = FIELDS.slice();

    // Build list of columns
    var head_row = ['District'],
        all_rows = [head_row],
        field, current_row, field_missing;
    
    if(has_incumbency) {
        head_row.push('Candidate Scenario');
    }

    if(plan.districts.length == 0)
    {
        return undefined;
    }
    
    for(var j = 0; j < plan.districts.length; j++)
    {
        var new_row = [(j + 1).toString()];
        
        if(has_incumbency) {
            new_row.push(incumbency[plan.incumbents[j]]);
        }

        all_rows.push(new_row);
    }
    
    for(var i in fields)
    {
        field = fields[i];
        field_missing = false;
        
        for(var j in plan.districts)
        {
            if(field in plan.districts[j].totals) {
                continue;
            } else if('compactness' in plan.districts[j] && field in plan.districts[j].compactness) {
                continue;
            } else {
                field_missing = true;
            }
        }
        
        if(field_missing) {
            continue;
        }
        
        head_row.push(field);

        for(var j in plan.districts)
        {
            current_row = all_rows[parseInt(j) + 1];
        
            if(field in plan.districts[j].totals) {
                current_row.push(plan.districts[j].totals[field]);

            } else if('compactness' in plan.districts[j] && field in plan.districts[j].compactness) {
                current_row.push(plan.districts[j].compactness[field]);
            }
        }
    }
    
    for(var j = 1; j < all_rows.length; j++)
    {
        update_vote_percentages(head_row, all_rows[j], plan.districts[j - 1].totals);
        update_acs2015_percentages(head_row, all_rows[j]);
        update_acs2016_percentages(head_row, all_rows[j]);
        update_acs2018_percentages(head_row, all_rows[j]);
        update_acs2019_percentages(head_row, all_rows[j]);
        update_cvap2015_percentages(head_row, all_rows[j]);
        update_cvap2018_percentages(head_row, all_rows[j]);
        update_cvap2019_percentages(head_row, all_rows[j]);
    }
    
    update_heading_titles(head_row);
    return all_rows;
}

function plan_voteshare(plan)
{
    var red_votes = 0, blue_votes = 0,
        red_fields = ['Republican Votes'],
        blue_fields = ['Democratic Votes'];

    for(var i in plan.districts)
    {
        for(var j in red_fields)
        {
            if(red_fields[j] in plan.districts[i].totals)
            {
                red_votes += plan.districts[i].totals[red_fields[j]];
            }
        }

        for(var k in blue_fields)
        {
            if(blue_fields[k] in plan.districts[i].totals)
            {
                blue_votes += plan.districts[i].totals[blue_fields[k]];
            }
        }
    }
    
    return Math.abs(blue_votes - red_votes) / (blue_votes + red_votes);
}

function nice_plan_voteshare(plan)
{
    var red_votes = 0, blue_votes = 0,
        red_fields = ['Republican Votes'],
        blue_fields = ['Democratic Votes'];

    for(var i in plan.districts)
    {
        for(var j in red_fields)
        {
            if(red_fields[j] in plan.districts[i].totals)
            {
                red_votes += plan.districts[i].totals[red_fields[j]];
            }
        }

        for(var k in blue_fields)
        {
            if(blue_fields[k] in plan.districts[i].totals)
            {
                blue_votes += plan.districts[i].totals[blue_fields[k]];
            }
        }
    }
    
    return (nice_percent(blue_votes / (blue_votes + red_votes)) + ' (Democratic) '
        + 'and ' + nice_percent(red_votes / (blue_votes + red_votes)) + ' (Republican)');
}

function get_description(plan, modified_at)
{
    var states = {
        'XX': 'Null Island',
        'AL': 'Alabama', 'NE': 'Nebraska', 'AK': 'Alaska', 'NV': 'Nevada',
        'AZ': 'Arizona', 'NH': 'New Hampshire', 'AR': 'Arkansas',
        'NJ': 'New Jersey', 'CA': 'California', 'NM': 'New Mexico',
        'CO': 'Colorado', 'NY': 'New York', 'CT': 'Connecticut',
        'NC': 'North Carolina', 'DE': 'Delaware', 'ND': 'North Dakota',
        'DC': 'District of Columbia', 'OH': 'Ohio', 'FL': 'Florida',
        'OK': 'Oklahoma', 'GA': 'Georgia', 'OR': 'Oregon', 'HI': 'Hawaii',
        'PA': 'Pennsylvania', 'ID': 'Idaho', 'PR': 'Puerto Rico',
        'IL': 'Illinois', 'RI': 'Rhode Island', 'IN': 'Indiana',
        'SC': 'South Carolina', 'IA': 'Iowa', 'SD': 'South Dakota',
        'KS': 'Kansas', 'TN': 'Tennessee', 'KY': 'Kentucky', 'TX': 'Texas',
        'LA': 'Louisiana', 'UT': 'Utah', 'ME': 'Maine', 'VT': 'Vermont',
        'MD': 'Maryland', 'VA': 'Virginia', 'MA': 'Massachusetts',
        'VI': 'Virgin Islands', 'MI': 'Michigan', 'WA': 'Washington',
        'MN': 'Minnesota', 'WV': 'West Virginia', 'MS': 'Mississippi',
        'WI': 'Wisconsin', 'MO': 'Missouri', 'WY': 'Wyoming',
        'MT': 'Montana'
        };
    
    var description = ['Plan uploaded'], houses = {'ushouse': 'U.S. House',
        'statesenate': 'State Senate', 'statehouse': 'State House'};
    
    if(plan['start_time'])
    {
        modified_at = new Date(plan.start_time * 1000);
    }
    
    if(plan['model'])
    {
        description = [states[plan.model.state],
            houses[plan.model.house], 'plan uploaded'].join(' ');
    }

    return (date_age(modified_at) > 86400)
            ? [description, 'on', modified_at.toLocaleDateString()].join(' ')
            : [description, 'at', modified_at.toLocaleString()].join(' ');
}

function load_plan_score(url, message_section, score_section,
    description, model_link, model_url_pattern, table, score_EG, score_PB,
    score_MM, score_sense, text_url, text_link, geom_prefix, map_div)
{
    var request = new XMLHttpRequest();
    request.open('GET', url, true);

    show_message('Loading district plan…', score_section, message_section);

    function on_loaded_score(plan, modified_at)
    {
        if(which_score_summary_name(plan) === null) {
            show_message(plan['message'] ? plan.message : 'District plan failed to load.',
                score_section, message_section);
            return;

        } else {
            hide_message(score_section, message_section);
        }

        // Clear out and repopulate description.
        clear_element(description);
        if(what_score_description_text(plan)) {
            description.appendChild(document.createElement('p'));
            description.lastChild.appendChild(
                document.createTextNode(what_score_description_text(plan)));
        }
        description.appendChild(document.createElement('i'));
        description.lastChild.appendChild(
            document.createTextNode(get_description(plan, modified_at)));
        
        if(plan.model && (plan.model.version == '2017' || !plan.model.version)) {
            model_link.href = model_url_pattern.replace('data/2020', plan.model.key_prefix);
        
        } else if(plan.model && plan.model.version) {
            model_link.href = model_url_pattern.replace('2020', plan.model.version);
        }

        // Build the results table
        var table_array = plan_array(plan),
            tags, value;
        
        tags = ['<thead>', '<tr>'];
        for(var j = 0; j < table_array[0].length; j++)
        {
            tags = tags.concat(['<th>', table_array[0][j], '</th>']);
        }
        tags = tags.concat(['</tr>', '</thead>', '<tbody>']);
        for(var i = 1; i < table_array.length; i++)
        {
            tags = tags.concat(['<tr>']);
            for(var j = 0; j < table_array[i].length; j++)
            {
                if(typeof table_array[i][j] == 'number') {
                    value = nice_count(table_array[i][j]);
                } else if(typeof table_array[i][j] == 'string') {
                    value = nice_string(table_array[i][j]);
                } else {
                    value = '???';
                }
                tags = tags.concat(['<td>', value, '</td>']);
            }
            tags = tags.concat(['</tr>']);
        }

        tags = tags.concat(['</tbody>']);
        table.innerHTML = tags.join('');
        text_link.href = text_url;
        
        // Populate scores.
        show_efficiency_gap_score(plan, score_EG);
        show_sensitivity_test(plan, score_sense);
        
        if(plan_voteshare(plan) < .1 || location.hash.match(/\bshowall\b/)) {
            show_partisan_bias_score(plan, score_PB);
            show_mean_median_score(plan, score_MM);
        } else {
            hide_score_with_reason(score_PB,
                'The parties’ statewide vote shares are ' + nice_plan_voteshare(plan) + ' based on the model.'
                + ' Partisan bias is shown only where the parties’ statewide vote shares fall between 45% and 55%.'
                + ' Outside this range the metric’s assumptions are not plausible.');
            hide_score_with_reason(score_MM,
                'The parties’ statewide vote shares are ' + nice_plan_voteshare(plan) + ' based on the model.'
                + ' The mean-median difference is shown only where the parties’ statewide vote shares fall between 45% and 55%.'
                + ' Outside this range the metric’s assumptions are not plausible.');
        }

        // Go on to load the map.
        load_plan_map(geom_prefix + plan.geometry_key, map_div, plan);
    }

    request.onload = function()
    {
        if(request.status >= 200 && request.status < 400)
        {
            // Returns a dictionary with a list of districts
            var data = JSON.parse(request.responseText),
                modified_at = new Date(request.getResponseHeader('Last-Modified'));
            console.log('Loaded plan:', data);

            // older uploads had geometries but did not include geometry_key
            if(!('geometry_key' in data)) {
                console.log('Added geometry_key in post');
                data.geometry_key = 'uploads/' + data.id + '/geometry.json';
            }
        
            on_loaded_score(data, modified_at);
            return;
        }
        
        show_message('The district plan failed to load.', score_section, message_section);
    };

    request.onerror = function() { /* There was a connection error of some sort */ };
    request.send();
}

function load_plan_map(url, div, plan)
{
    var request = new XMLHttpRequest();
    request.open('GET', url, true);

    function on_loaded_geojson(data)
    {
        function district_popup_content(layer)
        {
            var index = data.features.indexOf(layer.feature),
                incumbency = {'O': 'Open Seat', 'D': 'Democratic Incumbent', 'R': 'Republican Incumbent'},
                has_incumbency = (plan.model && plan.model.incumbency 
                    && plan.incumbents && plan.incumbents.length == plan.districts.length);

            if(has_incumbency) {
                return 'District ' + (index + 1) + '<br>' + incumbency[plan.incumbents[index]];
            }

            return 'District ' + (index + 1);
        }

        var geojson = L.geoJSON(data, {
            style: function(feature)
            {
                var district = plan.districts[data.features.indexOf(feature)];
                return { weight: 2, fillOpacity: .5, color: which_district_color(district, plan) };
            }
            }).bindPopup(district_popup_content);

        console.log('GeoJSON bounds:', geojson.getBounds());

        // 
        var show_leans = (typeof plan.districts[0].totals['Democratic Wins'] === 'number');
        add_map_pattern_support(show_leans);

        // Initialize the map on the passed div in the middle of the ocean
        var map = L.map(div, {
            scrollWheelZoom: false,
            zoomControl: false,
            center: [0, 0],
            zoom: 8
        });

        var pane = map.createPane('labels');
        pane.style.zIndex = 650; // http://leafletjs.com/examples/map-panes/
        pane.style.pointerEvents = 'none';

        // Add Toner tiles for base map
        L.tileLayer('https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_nolabels/{z}/{x}/{y}{r}.png', {
            attribution: '&copy;<a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>, &copy;<a href="https://carto.com/attribution">CARTO</a>',
            maxZoom: 18
        }).addTo(map);

        // Add a GeoJSON layer and fit it into view
        geojson.addTo(map);
        map.fitBounds(geojson.getBounds());

        // Add Toner label tiles for base map
        L.tileLayer('https://stamen-tiles.a.ssl.fastly.net/toner-labels/{z}/{x}/{y}{r}.png', {
            attribution: '&copy;<a href="http://stamen.com/">Stamen</a>',
            pane: 'labels',
            maxZoom: 18
        }).addTo(map);
        
        map.addControl(L.control.zoom({'position': 'topright'}));
        map.addControl(new L.Control.PartyLegend({'position': 'topleft'}));
    }

    request.onload = function()
    {
        if(request.status >= 200 && request.status < 400)
        {
            // Returns a GeoJSON dictionary
            var data = JSON.parse(request.responseText);
            console.log('Loaded map:', data);
            on_loaded_geojson(data);
        }
    };

    request.onerror = function() { /* There was a connection error of some sort */ };
    request.send();
}

function add_map_pattern_support(show_leans)
{
    // Custom map legend control copied from
    // https://github.com/PlanScore/PlanScore/blob/b48188b/_common/jslibs/leaflet-control-partylegend.js
    L.Control.PartyLegend = L.Control.extend({
        options: {
            position: 'topright',
        },

        initialize: function(options) {
            L.Util.setOptions(this, options);
        },

        onAdd: function (map) {
            var container = L.DomUtil.create('div', 'planscore-partylegend');

            var row_d    = L.DomUtil.create('div', 'planscore-partylegend-legend', container);
            var swatch_d = L.DomUtil.create('div', 'planscore-partylegend-swatch planscore-partylegend-swatch-democrat', row_d);
            var words_d  = L.DomUtil.create('div', 'planscore-partylegend-words', row_d);
            words_d.innerHTML = 'Democratic';

            var row_r    = L.DomUtil.create('div', 'planscore-partylegend-legend', container);
            var swatch_r = L.DomUtil.create('div', 'planscore-partylegend-swatch planscore-partylegend-swatch-republican', row_r);
            var words_r  = L.DomUtil.create('div', 'planscore-partylegend-words', row_r);
            words_r.innerHTML = 'Republican';

            if(show_leans)
            {
                var row_ld    = L.DomUtil.create('div', 'planscore-partylegend-legend', container);
                var swatch_ld = L.DomUtil.create('div', 'planscore-partylegend-swatch planscore-partylegend-swatch-lean-democrat', row_ld);
                var words_ld  = L.DomUtil.create('div', 'planscore-partylegend-words', row_ld);
                words_ld.innerHTML = 'Leans Dem.';

                var row_lr    = L.DomUtil.create('div', 'planscore-partylegend-legend', container);
                var swatch_lr = L.DomUtil.create('div', 'planscore-partylegend-swatch planscore-partylegend-swatch-lean-republican', row_lr);
                var words_lr  = L.DomUtil.create('div', 'planscore-partylegend-words', row_lr);
                words_lr.innerHTML = 'Leans Rep.';

            } else {
                var row_x    = L.DomUtil.create('div', 'planscore-partylegend-legend', container);
                var swatch_x = L.DomUtil.create('div', 'planscore-partylegend-swatch planscore-partylegend-swatch-both', row_x);
                var words_x  = L.DomUtil.create('div', 'planscore-partylegend-words', row_x);
                words_x.innerHTML = 'Uncertain';

                /*
                var row_0    = L.DomUtil.create('div', 'planscore-partylegend-legend', container);
                var swatch_0 = L.DomUtil.create('div', 'planscore-partylegend-swatch planscore-partylegend-swatch-nodata', row_0);
                var words_0  = L.DomUtil.create('div', 'planscore-partylegend-words', row_0);
                words_0.innerHTML = 'No Data';
                */
            }

            return container;
        },
    });

    if(L.Browser.svg)
    {
        L.SVG.include({
        
            // Exact copy of Leaflet SVG _updateStyle with additional awareness of unknown color
            // https://github.com/Leaflet/Leaflet/blob/b1e59c9/src/layer/vector/SVG.js#L141-L176
            _updateStyle: function _updateStyle(layer) {
                var path = layer._path,
                    options = layer.options;

                if (!path) { return; }

                if (options.stroke) {
                    path.setAttribute('stroke', options.color);
                    path.setAttribute('stroke-opacity', options.opacity);
                    path.setAttribute('stroke-width', options.weight);
                    path.setAttribute('stroke-linecap', options.lineCap);
                    path.setAttribute('stroke-linejoin', options.lineJoin);

                    if (options.dashArray) {
                        path.setAttribute('stroke-dasharray', options.dashArray);
                    } else {
                        path.removeAttribute('stroke-dasharray');
                    }

                    if (options.dashOffset) {
                        path.setAttribute('stroke-dashoffset', options.dashOffset);
                    } else {
                        path.removeAttribute('stroke-dashoffset');
                    }
                } else {
                    path.setAttribute('stroke', 'none');
                }

                if (options.fill)
                {
                    var pattern_colors = [UNKNOWN_COLOR_HEX, REDDISH_COLOR_HEX,
                        BLUEISH_COLOR_HEX, LEAN_BLUE_COLOR_HEX, LEAN_RED_COLOR_HEX];
                
                    if (typeof options.color == "string" && pattern_colors.indexOf(options.color) >= 0) {
                        // Add support for unknown color, a gray
                        this.__fillPattern(layer);
                    } else {
                        path.setAttribute('fill', options.fillColor || options.color);
                    }
                    path.setAttribute('fill-opacity', options.fillOpacity);
                    path.setAttribute('fill-rule', options.fillRule || 'evenodd');
                } else {
                    path.setAttribute('fill', 'none');
                }
            },

            // Close adaptation of __fillPattern from PlanScore static site visualization
            // https://github.com/PlanScore/PlanScore/blob/b48188b/_common/jslibs/leaflet-polygon.fillPattern.js
            __fillPattern: function __fillPattern(layer) {
                var path = layer._path,
                    options = layer.options;

                if (!this._defs) {
                    this._defs = L.SVG.create('defs');
                    this._container.appendChild(this._defs);
                }
                
                if(options.color == UNKNOWN_COLOR_HEX) {
                    var _img_url = UNKNOWN_PATTERN_URL;
                    var _ref_id = 'UNKNOWN_PATTERN_URL' + new Date().getUTCMilliseconds();
                } else if(options.color == LEAN_RED_COLOR_HEX) {
                    var _img_url = LEAN_RED_PATTERN_URL;
                    var _ref_id = 'LEAN_RED_PATTERN_URL' + new Date().getUTCMilliseconds();
                } else if(options.color == LEAN_BLUE_COLOR_HEX) {
                    var _img_url = LEAN_BLUE_PATTERN_URL;
                    var _ref_id = 'LEAN_BLUE_PATTERN_URL' + new Date().getUTCMilliseconds();
                } else if(options.color == REDDISH_COLOR_HEX) {
                    var _img_url = REDDISH_PATTERN_URL;
                    var _ref_id = 'REDDISH_PATTERN_URL' + new Date().getUTCMilliseconds();
                } else if(options.color == BLUEISH_COLOR_HEX) {
                    var _img_url = BLUEISH_PATTERN_URL;
                    var _ref_id = 'BLUEISH_PATTERN_URL' + new Date().getUTCMilliseconds();
                }
                
                var _p = document.getElementById(_ref_id);
                if (!_p) {
                    var _im = new Image();
                    _im.src = _img_url;

                    _p = L.SVG.create('pattern');
                    _p.setAttribute('id', _ref_id);
                    _p.setAttribute('x', '0');
                    _p.setAttribute('y', '0');
                    _p.setAttribute('patternUnits', 'userSpaceOnUse');
                    _p.setAttribute('width', '24');
                    _p.setAttribute('height', '24');
                    var _rect = L.SVG.create('rect');
                    _rect.setAttribute('width', 24);
                    _rect.setAttribute('height', 24);
                    _rect.setAttribute('x', 0);
                    _rect.setAttribute('x', 0);
                    _rect.setAttribute('fill', options.fillColor || options.color);

                    _p.appendChild(_rect);
                    this._defs.appendChild(_p);

                    var _img = L.SVG.create('image');
                    _img.setAttribute('x', '0');
                    _img.setAttribute('y', '0');
                    _img.setAttributeNS('http://www.w3.org/1999/xlink', 'href', _img_url);
                    _img.setAttribute('width', '24');
                    _img.setAttribute('height', '24');
                    _p.appendChild(_img);

                    _im.onload = function () {
                        _p.setAttribute('width', _im.width);
                        _p.setAttribute('height', _im.height);
                        _img.setAttribute('width', _im.width);
                        _img.setAttribute('height', _im.height);
                    };
                }
                path.setAttribute('fill', "url(#" + _ref_id + ")");
            }
        });
    }
}

// Export functions for testing
if(typeof module !== 'undefined' && module.exports)
{
    module.exports = {
        format_url: format_url, nice_count: nice_count, nice_string: nice_string,
        nice_percent: nice_percent, nice_round_percent: nice_round_percent,
        nice_gap: nice_gap, date_age: date_age,
        what_score_description_text: what_score_description_text,
        which_score_summary_name: which_score_summary_name,
        which_score_column_names: which_score_column_names,
        which_district_color: which_district_color,
        plan_array: plan_array, get_description: get_description,
        update_vote_percentages: update_vote_percentages,
        update_acs2015_percentages: update_acs2015_percentages,
        update_acs2016_percentages: update_acs2016_percentages,
        update_cvap2015_percentages: update_cvap2015_percentages,
        update_heading_titles: update_heading_titles
        };
}
