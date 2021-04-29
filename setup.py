from setuptools import setup

setup(
    name = 'PlanScore',
    url = 'https://github.com/migurski/PlanScore',
    author = 'Michal Migurski',
    description = '',
    packages = [
        'planscore', 'planscore.website', 'planscore.tests', 'planscore.compactness'
        ],
    test_suite = 'planscore.tests',
    package_data = {
        'planscore': ['geodata/*.*', 'model/*.csv.gz'],
        'planscore.website': ['templates/*.html', 'static/*.*'],
        'planscore.tests': [
            'data/*.*',
            'data/*/*/*/*.geojson',
            'data/*/tiles/*/*/*.geojson',
            'data/*-graphs/*/*.pickle',
            'data/uploads/sample-plan/districts/?.json',
            'data/uploads/sample-plan/tiles/*/*/*.json',
            'data/uploads/sample-plan/geometries/?.wkt'
            ],
        },
    install_requires = [
        'boto3 == 1.17.60',
        'Flask == 0.12.2',
        'itsdangerous == 0.24',
        'Jinja2 == 2.11.3',
        'Markdown == 2.6.8',
        'ModestMaps == 1.4.7',
        'networkx == 2.5',
        'Shapely == 1.7.1',
        ],
    extras_require = {
        'compiled': [
            'GDAL == 2.1.3',
            'numpy == 1.19.2',
            ],
        'deploy': [
            'aws-cdk.aws-apigateway == 1.101.0',
            'aws-cdk.aws-certificatemanager == 1.101.0',
            'aws-cdk.aws-cloudfront == 1.101.0',
            'aws-cdk.aws-cloudfront-origins == 1.101.0',
            'aws-cdk.aws-iam == 1.101.0',
            'aws-cdk.aws-lambda == 1.101.0',
            'aws-cdk.aws-logs == 1.101.0',
            'aws-cdk.aws-s3 == 1.101.0',
            'aws-cdk.aws-s3-deployment == 1.101.0',
            'aws-cdk.core == 1.101.0',
            'Frozen-Flask == 0.14',
            ],
        },
    entry_points = dict(
        console_scripts = [
            'planscore-matrix-debug = planscore.matrix:main',
            'planscore-polygonize = planscore.polygonize:main',
            'planscore-prepare-state = planscore.prepare_state:main',
            'planscore-score-locally = planscore.score:main',
            ]
        ),
)
