import boto3, botocore.exceptions, time, json, posixpath, io, gzip, collections
from . import data, constants, tiles

FUNCTION_NAME = 'PlanScore-ObserveTiles'

def put_upload_index(storage, upload):
    ''' Save a JSON index and a plaintext file for this upload.
    '''
    key1 = 'uploads/{}/index-tiles.json'.format(upload.id)
    body1 = upload.to_json().encode('utf8')

    storage.s3.put_object(Bucket=storage.bucket, Key=key1, Body=body1,
        ContentType='text/json', ACL='public-read')

    return
    
    key2 = upload.plaintext_key()
    body2 = upload.to_plaintext().encode('utf8')

    storage.s3.put_object(Bucket=storage.bucket, Key=key2, Body=body2,
        ContentType='text/plain', ACL='public-read')

def get_expected_tile(enqueued_key, upload):
    ''' Return an expect tile key for an enqueued one.
    '''
    return data.UPLOAD_TILES_KEY.format(id=upload.id,
        zxy=tiles.get_tile_zxy(upload.model.key_prefix, enqueued_key))

def get_district_index(geometry_key, upload):
    ''' Return numeric index for a given geometry key.
    '''
    dirname = posixpath.dirname(data.UPLOAD_GEOMETRIES_KEY).format(id=upload.id)
    base, _ = posixpath.splitext(posixpath.relpath(geometry_key, dirname))
    
    return int(base)

def iterate_totals(expected_tiles, storage, upload, context):
    '''
    '''
    next_update = time.time()

    # Look for each expected tile in turn
    for (index, expected_tile) in enumerate(expected_tiles):
        progress = data.Progress(index, len(expected_tiles))
        upload = upload.clone(progress=progress,
            message='Scoring this newly-uploaded plan. {} of {} parts'
                ' complete. Reload this page to see the result.'.format(*progress.to_list()))

        # Update S3, if it's time
        if time.time() > next_update:
            put_upload_index(storage, upload)
            next_update = time.time() + 3

        # Wait for one expected tile
        while True:
            try:
                object = storage.s3.get_object(Bucket=storage.bucket, Key=expected_tile)
            except botocore.exceptions.ClientError:
                # Did not find the expected tile, wait a little before checking
                time.sleep(3)
            else:
                if object.get('ContentEncoding') == 'gzip':
                    object['Body'] = io.BytesIO(gzip.decompress(object['Body'].read()))
        
                yield json.load(object['Body']).get('totals')
            
                # Found the expected tile, break out of this loop
                break

            remain_msec = context.get_remaining_time_in_millis()

            if remain_msec < 5000:
                # Out of time, just stop
                overdue_upload = upload.clone(message="Giving up on this plan after it took too long, sorry.")
                put_upload_index(storage, overdue_upload)
                return

def accumulate_totals(input_totals, upload):
    '''
    '''
    output_totals = collections.defaultdict(lambda: collections.defaultdict(float))
    
    for input_total in input_totals:
        for (geometry_key, input_values) in input_total.items():
            geometry_index = get_district_index(geometry_key, upload)
            output_total = output_totals[geometry_index]
            for (key, value) in input_values.items():
                output_total[key] = round(output_total[key] + value, constants.ROUND_COUNT)
    
    return [output_total for (_, output_total) in sorted(output_totals.items())]

def lambda_handler(event, context):
    '''
    '''
    s3 = boto3.client('s3', endpoint_url=constants.S3_ENDPOINT_URL)
    storage = data.Storage.from_event(event['storage'], s3)
    upload = data.Upload.from_dict(event['upload'])
    
    obj = storage.s3.get_object(Bucket=storage.bucket,
        Key=data.UPLOAD_TILE_INDEX_KEY.format(id=upload.id))
    
    enqueued_tiles = json.load(obj['Body'])
    expected_tiles = [get_expected_tile(tile_key, upload)
        for tile_key in enqueued_tiles]
    
    next_update = time.time()

    # Look for each expected tile in turn
    for (index, expected_tile) in enumerate(expected_tiles):
        progress = data.Progress(index, len(expected_tiles))
        upload = upload.clone(progress=progress,
            message='Scoring this newly-uploaded plan. {} of {} parts'
                ' complete. Reload this page to see the result.'.format(*progress.to_list()))

        # Update S3, if it's time
        if time.time() > next_update:
            put_upload_index(storage, upload)
            next_update = time.time() + 3

        # Wait for one expected tile
        while True:
            try:
                resp = storage.s3.get_object(Bucket=storage.bucket, Key=expected_tile)
            except botocore.exceptions.ClientError:
                # Did not find the expected tile, wait a little before checking
                time.sleep(3)
            else:
                print(expected_tile, json.load(resp['Body']).keys())
            
                # Found the expected tile, break out of this loop
                break

            remain_msec = context.get_remaining_time_in_millis()

            if remain_msec < 5000:
                # Out of time, just stop
                overdue_upload = upload.clone(message="Giving up on this plan after it took too long, sorry.")
                put_upload_index(storage, overdue_upload)
                return

    complete_upload = upload.clone(message='Finished scoring this plan.',
        progress=data.Progress(len(expected_tiles), len(expected_tiles)))

    put_upload_index(storage, complete_upload)
