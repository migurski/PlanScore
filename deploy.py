#!/usr/bin/env python
import sys, argparse, boto3, os, copy, time, random, subprocess
import botocore.exceptions

git_commit_sha = subprocess.check_output(('git', 'rev-parse', 'HEAD')).strip().decode('ascii')

common = {
    'Runtime': 'python3.6',
    'Environment': {
        'Variables': {
            'GIT_COMMIT_SHA': git_commit_sha,
        },
    },
}

if 'AWS_LAMBDA_DLQ_ARN' in os.environ:
    common.update(DeadLetterConfig=dict(TargetArn=os.environ['AWS_LAMBDA_DLQ_ARN']))

functions = {
    'PlanScore-Authorizer': dict(Handler='lambda.authorizer', Timeout=3, **common),
    'PlanScore-APIUpload': dict(Handler='lambda.api_upload', Timeout=300, MemorySize=2048, **common),
    'PlanScore-UploadFields': dict(Handler='lambda.upload_fields', Timeout=3, **common),
    'PlanScore-UploadFieldsNew': dict(Handler='lambda.upload_fields_new', Timeout=3, **common),
    'PlanScore-Preread': dict(Handler='lambda.preread', Timeout=3, **common),
    'PlanScore-PrereadFollowup': dict(Handler='lambda.preread_followup', Timeout=300, MemorySize=1024, **common),
    'PlanScore-PostreadCallback': dict(Handler='lambda.postread_callback', Timeout=300, MemorySize=1024, **common),
    'PlanScore-PostreadCalculate': dict(Handler='lambda.postread_calculate', Timeout=300, MemorySize=1024, **common),
    'PlanScore-Callback': dict(Handler='lambda.callback', Timeout=3, **common),
    'PlanScore-AfterUpload': dict(Handler='lambda.after_upload', Timeout=300, MemorySize=1024, **common),
    'PlanScore-RunTile': dict(Handler='lambda.run_tile', Timeout=300, MemorySize=2048, **common),
    'PlanScore-ObserveTiles': dict(Handler='lambda.observe_tiles', Timeout=300, MemorySize=512, **common),
    }

api_paths = {
    'PlanScore-APIUpload': 'api-upload',
    'PlanScore-UploadFields': 'upload',
    'PlanScore-Callback': 'uploaded',
    'PlanScore-UploadFieldsNew': 'upload-new',
    'PlanScore-PostreadCallback': 'uploaded-new',
    'PlanScore-Preread': 'preread',
    }

api_methods = {
    'PlanScore-APIUpload': dict(httpMethod='POST', authorizationType='NONE',
        #requestParameters={},
        ),
    'PlanScore-UploadFields': dict(httpMethod='GET', authorizationType='NONE',
        #requestParameters={'method.request.querystring.incumbency': True},
        ),
    'PlanScore-UploadFieldsNew': dict(httpMethod='GET', authorizationType='NONE',
        #requestParameters={'method.request.querystring.incumbency': True},
        ),
    'PlanScore-Preread': dict(httpMethod='GET', authorizationType='NONE',
        #requestParameters={
        #    'method.request.querystring.id': True,
        #    'method.request.querystring.bucket': True,
        #    'method.request.querystring.key': True,
        #    'method.request.querystring.incumbency': True,
        #    },
        ),
    'PlanScore-PostreadCallback': dict(httpMethod='GET', authorizationType='NONE',
        #requestParameters={
        #    'method.request.querystring.id': True,
        #    'method.request.querystring.bucket': True,
        #    'method.request.querystring.key': True,
        #    'method.request.querystring.incumbency': True,
        #    },
        ),
    'PlanScore-Callback': dict(httpMethod='GET', authorizationType='NONE',
        #requestParameters={
        #    'method.request.querystring.id': True,
        #    'method.request.querystring.bucket': True,
        #    'method.request.querystring.key': True,
        #    'method.request.querystring.incumbency': True,
        #    },
        ),
    }

api_integrations = {
    'PlanScore-APIUpload': dict(httpMethod='POST',
        #requestParameters={},
        ),
    'PlanScore-UploadFields': dict(httpMethod='GET',
        #requestParameters={'integration.request.querystring.incumbency': 'method.request.querystring.incumbency'},
        ),
    'PlanScore-UploadFieldsNew': dict(httpMethod='GET',
        #requestParameters={'integration.request.querystring.incumbency': 'method.request.querystring.incumbency'},
        ),
    'PlanScore-Preread': dict(httpMethod='GET',
        #requestParameters={
        #    'integration.request.querystring.id': 'method.request.querystring.id',
        #    'integration.request.querystring.bucket': 'method.request.querystring.bucket',
        #    'integration.request.querystring.key': 'method.request.querystring.key',
        #    'integration.request.querystring.incumbency': 'method.request.querystring.incumbency',
        #    },
        ),
    'PlanScore-PostreadCallback': dict(httpMethod='GET',
        #requestParameters={
        #    'integration.request.querystring.id': 'method.request.querystring.id',
        #    'integration.request.querystring.bucket': 'method.request.querystring.bucket',
        #    'integration.request.querystring.key': 'method.request.querystring.key',
        #    'integration.request.querystring.incumbency': 'method.request.querystring.incumbency',
        #    },
        ),
    'PlanScore-Callback': dict(httpMethod='GET',
        #requestParameters={
        #    'integration.request.querystring.id': 'method.request.querystring.id',
        #    'integration.request.querystring.bucket': 'method.request.querystring.bucket',
        #    'integration.request.querystring.key': 'method.request.querystring.key',
        #    'integration.request.querystring.incumbency': 'method.request.querystring.incumbency',
        #    },
        ),
    }

# "Dev"-prefixed version of each function
functions.update({f'Dev-{k}': v for (k, v) in functions.items()})
api_paths.update({f'Dev-{k}': v for (k, v) in api_paths.items()})
api_methods.update({f'Dev-{k}': v for (k, v) in api_methods.items()})
api_integrations.update({f'Dev-{k}': v for (k, v) in api_integrations.items()})

def publish_function(lam, name, code_dict, env, role):
    ''' Create or update the named function to Lambda, return its ARN.
    '''
    start_time = time.time()
    function_kwargs = copy.deepcopy(functions[name])
    function_kwargs['Environment']['Variables'].update(env)
    
    if role is not None:
        function_kwargs.update(Role=role)

    try:
        print('    * get function', name, file=sys.stderr)
        lam.get_function(FunctionName=name)
    except botocore.exceptions.ClientError:
        # Function does not exist, create it
        print('    * create function', name, file=sys.stderr)
        lam.create_function(FunctionName=name, Code=code_dict, **function_kwargs)
    else:
        # Function exists, update it
        print('    * update function code', name, file=sys.stderr)
        lam.update_function_code(FunctionName=name, **code_dict)
        print('    * update function configuration', name, file=sys.stderr)
        lam.update_function_configuration(FunctionName=name, **function_kwargs)
    
    arn = lam.get_function_configuration(FunctionName=name).get('FunctionArn')
    print('    * done with {} in {:.1f} seconds'.format(arn, time.time() - start_time), file=sys.stderr)
    
    return arn

def prepare_api(api, api_name):
    '''
    '''
    try:
        print('    * get API', api_name, file=sys.stderr)
        rest_api = [item for item in api.get_rest_apis()['items']
            if item['name'] == api_name][0]
    except:
        print('    * create API', api_name, file=sys.stderr)
        rest_api = api.create_rest_api(name=api_name)
    finally:
        rest_api_id = rest_api['id']
        top_level = [
            item for item
            in api.get_resources(restApiId=rest_api_id)['items']
            if item['path'] == '/'
        ][0]
        api_kwargs = dict(restApiId=rest_api_id, parentId=top_level['id'])
    
    return rest_api_id, api_kwargs

def update_api(api, api_name, function_arn, function_name, role):
    '''
    '''
    path = api_paths[function_name]
    rest_api_id, api_kwargs = prepare_api(api, api_name)
    
    try:
        print('    * get resource', rest_api_id, path, file=sys.stderr)
        resource = [item for item in api.get_resources(restApiId=rest_api_id)['items']
            if item['path'] == f'/{path}'][0]
    except:
        print('    * create resource', rest_api_id, path, file=sys.stderr)
        resource = api.create_resource(pathPart=path, **api_kwargs)
    finally:
        api_kwargs = dict(restApiId=rest_api_id, resourceId=resource['id'])
    
    try:
        print('    * put method', rest_api_id, api_methods[function_name]['httpMethod'], path, file=sys.stderr)
        api_methods[function_name].update(**api_kwargs)
        api.put_method(**api_methods[function_name])
    except:
        print('    * method exists?', rest_api_id, api_methods[function_name]['httpMethod'], path, file=sys.stderr)

    print('    * put integration', rest_api_id, api_integrations[function_name]['httpMethod'], path, file=sys.stderr)
    api_integrations[function_name].update(**api_kwargs)
    api.put_integration(credentials=role, type='AWS_PROXY',
        uri=f'arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/{function_arn}/invocations',
        integrationHttpMethod='POST', passthroughBehavior='WHEN_NO_MATCH',
        **api_integrations[function_name])

    print('    * done with', f'{api._endpoint.host}/restapis/{rest_api_id}/live/{path}', file=sys.stderr)

    for res in api.get_resources(restApiId=rest_api_id)['items']:
        if res['path'] != '/' and res['pathPart'] not in api_paths.values():
            print('    - deleting resource', res['id'], res['path'], file=sys.stderr)
            try:
                api.delete_resource(restApiId=rest_api_id, resourceId=res['id'])
            except:
                # Maybe someone else got to it first
                pass

    return rest_api_id

parser = argparse.ArgumentParser(description='Update Lambda function.')
parser.add_argument('path', help='Function code path')
parser.add_argument('apiname', help='API name')
parser.add_argument('s3bucket', help='S3 bucket name')
parser.add_argument('s3key', help='S3 object key')
parser.add_argument('name', help='Function name')

if __name__ == '__main__':
    args = parser.parse_args()
    role = os.environ.get('AWS_IAM_ROLE')
    lam = boto3.client('lambda', region_name='us-east-1')
    api = boto3.client('apigateway', region_name='us-east-1')
    
    env = {k: os.environ[k]
        for k in ('PLANSCORE_SECRET', 'WEBSITE_BASE', 'API_BASE')
        if k in os.environ}
    env['S3_BUCKET'] = args.s3bucket
    
    if 'PlanScore-Authorizer' in args.name and 'API_TOKENS' in os.environ:
        env['API_TOKENS'] = os.environ['API_TOKENS']
    
    code_dict = dict(S3Bucket=args.s3bucket, S3Key=args.s3key)
    arn = publish_function(lam, args.name, code_dict, env, role)
    if args.name not in api_methods:
        print('    - No API Gateway for', args.name, file=sys.stderr)
        exit()
    rest_api_id = update_api(api, args.apiname, arn, args.name, role)
    time.sleep(random.randint(0, 5))
