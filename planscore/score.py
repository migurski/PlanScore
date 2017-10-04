import io, os, gzip, posixpath, json, collections
from osgeo import ogr
import boto3, botocore.exceptions
from . import prepare_state, util, data, constants

ogr.UseExceptions()

FUNCTION_NAME = 'PlanScore-ScoreDistrictPlan'

def score_plan(s3, bucket, input_upload, plan_path, tiles_prefix):
    '''
    '''
    new_districts = []
    feature_count, output = 0, io.StringIO()
    ds = ogr.Open(plan_path)
    print(ds, file=output)
    
    if not ds:
        raise RuntimeError('Could not open file')
    
    for (index, feature) in enumerate(ds.GetLayer(0)):
        feature_count += 1
        print(index, feature, file=output)

        totals, tiles, district_output = score_district(s3, bucket, feature.GetGeometryRef(), tiles_prefix)
        output.write(district_output)
        new_districts.append(dict(totals=totals, tiles=tiles))
    
    output_upload = calculate_gap(input_upload.clone(districts=new_districts))
    length = os.stat(plan_path).st_size
    
    print('{} features in {}-byte {}'.format(feature_count,
        length, os.path.basename(plan_path)), file=output) 
    
    print('Uploading to s3://{}/{}...'.format(bucket, output_upload.index_key()),
        file=output)
    
    return output_upload, output.getvalue()

def score_district(s3, bucket, district_geom, tiles_prefix):
    '''
    '''
    tile_list, output = [], io.StringIO()
    totals = {field: 0 for field in data.FIELD_NAMES}
    
    if district_geom.GetSpatialReference():
        district_geom.TransformTo(prepare_state.EPSG4326)
    
    xxyy_extent = district_geom.GetEnvelope()
    tiles = prepare_state.iter_extent_tiles(xxyy_extent, prepare_state.TILE_ZOOM)

    for (coord, tile_wkt) in tiles:
        tile_zxy = '{zoom}/{column}/{row}'.format(**coord.__dict__)
        tile_geom = ogr.CreateGeometryFromWkt(tile_wkt)
        
        if not tile_geom.Intersects(district_geom):
            continue
        
        try:
            object = s3.get_object(Bucket='planscore',
                Key='{}/{}.geojson'.format(tiles_prefix, tile_zxy))
        except botocore.exceptions.ClientError as error:
            if error.response['Error']['Code'] == 'NoSuchKey':
                continue
            raise

        if object.get('ContentEncoding') == 'gzip':
            object['Body'] = io.BytesIO(gzip.decompress(object['Body'].read()))
        
        with util.temporary_buffer_file('tile.geojson', object['Body']) as path:
            ds = ogr.Open(path)
            defn = ds.GetLayer(0).GetLayerDefn()
            fields = [defn.GetFieldDefn(i).name for i in range(defn.GetFieldCount())]
            for feature in ds.GetLayer(0):
                precinct_geom = feature.GetGeometryRef()
                
                if not precinct_geom.Intersects(district_geom):
                    continue
                
                try:
                    overlap_geom = precinct_geom.Intersection(district_geom)
                except RuntimeError as e:
                    if 'TopologyException' in str(e) and not precinct_geom.IsValid():
                        # Sometimes, a precinct geometry can be invalid
                        # so inflate it by a tiny amount to smooth out problems
                        precinct_geom = precinct_geom.Buffer(0.0000001)
                        overlap_geom = precinct_geom.Intersection(district_geom)
                    else:
                        raise
                overlap_area = overlap_geom.Area() / precinct_geom.Area()
                precinct_fraction = overlap_area * feature.GetField(prepare_state.FRACTION_FIELD)
                
                for name in data.FIELD_NAMES:
                    if name not in fields:
                        continue
                    precinct_value = precinct_fraction * feature.GetField(name)
                    totals[name] += precinct_value
                
        tile_list.append(tile_zxy)
        print(' ', prepare_state.KEY_FORMAT.format(state='XX', version='.',
            zxy=tile_zxy), file=output)
    
    print('>', totals, file=output)
    
    return totals, tile_list, output.getvalue()

def calculate_gap(original_upload):
    ''' Return a copied Upload object with populated summary.
    '''
    gaps = {
        'Red/Blue': ('Red Votes', 'Blue Votes'),
        'US House': ('US House Rep Votes', 'US House Dem Votes'),
        'SLDU': ('SLDU Rep Votes', 'SLDU Dem Votes'),
        'SLDL': ('SLDL Rep Votes', 'SLDL Dem Votes'),
        }
    
    # Prepare dictionary of vote swings for sensitivity testing
    swings = {
        0.: original_upload,

        # +Red vote swings
        -.01: original_upload.swing(-.01),
        -.02: original_upload.swing(-.02),
        -.03: original_upload.swing(-.03),
        -.04: original_upload.swing(-.04),
        -.05: original_upload.swing(-.05),
        -.07: original_upload.swing(-.07),
        -.10: original_upload.swing(-.10),

        # +Blue vote swings
        .01: original_upload.swing(.01),
        .02: original_upload.swing(.02),
        .03: original_upload.swing(.03),
        .04: original_upload.swing(.04),
        .05: original_upload.swing(.05),
        .07: original_upload.swing(.07),
        .10: original_upload.swing(.10),
        }
        
    # Collect summaries with a variety of swing amounts
    swing_summaries = collections.defaultdict(dict)
    
    for (swing, upload) in swings.items():
        for (prefix, (red_field, blue_field)) in gaps.items():
            election_votes, wasted_red, wasted_blue, red_wins, blue_wins = 0, 0, 0, 0, 0

            for district in upload.districts:
                red_votes = district['totals'].get(red_field) or 0
                blue_votes = district['totals'].get(blue_field) or 0
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

            if election_votes > 0:
                efficiency_gap = (wasted_red - wasted_blue) / election_votes
            else:
                efficiency_gap = None

            key = 'Efficiency Gap' if (prefix == 'Red/Blue') else '{} Efficiency Gap'.format(prefix)
            swing_summaries[key][swing] = efficiency_gap
    
    summary_dict = dict(
        # Simple key=number for each non-swing vote count
        {key: swings[0.] for (key, swings) in swing_summaries.items()},

        # Additional dictionary of gaps at each swing value
        Swings={key: list(sorted(swings.items()))
            for (key, swings) in swing_summaries.items()}
        )
    
    return original_upload.clone(summary=summary_dict)

def put_upload_index(s3, bucket, upload):
    ''' Save a JSON index file for this upload.
    '''
    key = upload.index_key()
    body = upload.to_json().encode('utf8')

    s3.put_object(Bucket=bucket, Key=key, Body=body,
        ContentType='text/json', ACL='public-read')

def lambda_handler(event, context):
    '''
    '''
    print('event:', json.dumps(event))

    input_upload = data.Upload.from_dict(event)
    storage = data.Storage.from_event(event, boto3.client('s3', endpoint_url=constants.S3_ENDPOINT_URL))
    
    # Look for all expected districts.
    prefix = posixpath.dirname(input_upload.district_key(-1))
    listed_objects = storage.s3.list_objects(Bucket=storage.bucket, Prefix=prefix)
    existing_keys = [obj.get('Key') for obj in listed_objects.get('Contents', [])]
    
    new_districts = []
    
    for key in existing_keys:
        try:
            object = storage.s3.get_object(Bucket=storage.bucket, Key=key)
        except botocore.exceptions.ClientError as error:
            if error.response['Error']['Code'] == 'NoSuchKey':
                continue
            raise

        if object.get('ContentEncoding') == 'gzip':
            object['Body'] = io.BytesIO(gzip.decompress(object['Body'].read()))
        
        new_districts.append(json.load(object['Body']))

    output_upload = calculate_gap(input_upload.clone(districts=new_districts))
    put_upload_index(storage.s3, storage.bucket, output_upload)
