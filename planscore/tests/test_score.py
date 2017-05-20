import unittest, unittest.mock, io, os, contextlib, json, gzip, itertools
from .. import score, data
import botocore.exceptions
from osgeo import ogr

should_gzip = itertools.cycle([True, False])

def mock_s3_get_object(Bucket, Key):
    '''
    '''
    path = os.path.join(os.path.dirname(__file__), 'data', Key)
    if not os.path.exists(path):
        raise botocore.exceptions.ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
    with open(path, 'rb') as file:
        if next(should_gzip):
            return {'Body': io.BytesIO(gzip.compress(file.read())),
                'ContentEncoding': 'gzip'}
        else:
            return {'Body': io.BytesIO(file.read())}

class TestScore (unittest.TestCase):

    def test_score_district(self):
        '''
        '''
        s3, bucket = unittest.mock.Mock(), unittest.mock.Mock()
        s3.get_object.side_effect = mock_s3_get_object
        
        with open(os.path.join(os.path.dirname(__file__), 'data', 'null-plan.geojson')) as file:
            geojson = json.load(file)
        
        feature1, feature2 = geojson['features']

        geometry1 = ogr.CreateGeometryFromJson(json.dumps(feature1['geometry']))
        totals1, tiles1, _ = score.score_district(s3, bucket, geometry1, 'XX')

        geometry2 = ogr.CreateGeometryFromJson(json.dumps(feature2['geometry']))
        totals2, tiles2, _ = score.score_district(s3, bucket, geometry2, 'XX')
        
        self.assertAlmostEqual(totals1['Voters'] + totals2['Voters'], 15)
        self.assertAlmostEqual(totals1['Blue Votes'] + totals2['Blue Votes'], 6)
        self.assertAlmostEqual(totals1['Red Votes'] + totals2['Red Votes'], 6)
        self.assertEqual(tiles1, ['10/511/511', '10/511/512'])
        self.assertEqual(tiles2, ['10/511/511', '10/512/511', '10/511/512', '10/512/512'])
    
    def test_score_district_missing_tile(self):
        '''
        '''
        s3, bucket = unittest.mock.Mock(), unittest.mock.Mock()
        s3.get_object.side_effect = mock_s3_get_object
        
        with open(os.path.join(os.path.dirname(__file__), 'data', 'null-ranch.geojson')) as file:
            geojson = json.load(file)
        
        feature = geojson['features'][0]
        geometry = ogr.CreateGeometryFromJson(json.dumps(feature['geometry']))
        totals, tiles, _ = score.score_district(s3, bucket, geometry, 'XX')

        self.assertFalse(totals['Voters'])
        self.assertFalse(tiles)
    
    @unittest.mock.patch('planscore.score.score_district')
    def test_score_plan_geojson(self, score_district):
        '''
        '''
        score_district.return_value = {'Yo': 1}, ['zxy'], 'Better score a district.\n'
        
        plan_path = os.path.join(os.path.dirname(__file__), 'data', 'null-plan.geojson')
        upload = data.Upload('id', os.path.basename(plan_path), [])
        tiles_prefix = None
        
        scored, output = score.score_plan(None, None, upload, plan_path, tiles_prefix)
        self.assertIn('2 features in 1119-byte null-plan.geojson', output)
        self.assertIn('Better score a district.', output)
        self.assertEqual(scored.districts, [{'totals': {'Yo': 1}, 'tiles': ['zxy']}] * 2)
    
    @unittest.mock.patch('planscore.score.score_district')
    def test_score_plan_gpkg(self, score_district):
        '''
        '''
        score_district.return_value = {'Yo': 1}, ['zxy'], 'Better score a district.\n'
        
        plan_path = os.path.join(os.path.dirname(__file__), 'data', 'null-plan.gpkg')
        upload = data.Upload('id', os.path.basename(plan_path), [])
        tiles_prefix = None
        
        scored, output = score.score_plan(None, None, upload, plan_path, tiles_prefix)
        self.assertIn('2 features in 40960-byte null-plan.gpkg', output)
        self.assertIn('Better score a district.', output)
        self.assertEqual(scored.districts, [{'totals': {'Yo': 1}, 'tiles': ['zxy']}] * 2)
    
    def test_score_plan_bad_file_type(self):
        '''
        '''
        plan_path = __file__
        upload = data.Upload('id', os.path.basename(plan_path), [])
        tiles_prefix = None
        
        with self.assertRaises(RuntimeError) as error:
            score.score_plan(None, None, upload, plan_path, tiles_prefix)
    
    def test_score_plan_bad_file_content(self):
        '''
        '''
        plan_path = os.path.join(os.path.dirname(__file__), 'data', 'bad-data.geojson')
        upload = data.Upload('id', os.path.basename(plan_path), [])
        tiles_prefix = None
        
        with self.assertRaises(RuntimeError) as error:
            score.score_plan(None, None, upload, plan_path, tiles_prefix)
