import os, json, csv, io, time, enum, datetime
from . import constants

UPLOAD_PREFIX = 'uploads/{id}/upload/'
UPLOAD_INDEX_KEY = 'uploads/{id}/index.json'
UPLOAD_PLAINTEXT_KEY = 'uploads/{id}/index.txt'
UPLOAD_GEOMETRY_KEY = 'uploads/{id}/geometry.json'
UPLOAD_DISTRICTS_KEY = 'uploads/{id}/districts/{index}.json'
UPLOAD_GEOMETRIES_KEY = 'uploads/{id}/geometries/{index}.wkt'
UPLOAD_TILE_INDEX_KEY = 'uploads/{id}/tiles.json'
UPLOAD_TILES_KEY = 'uploads/{id}/tiles/{zxy}.json'
UPLOAD_TIMING_KEY = 'uploads/{id}/timing.csv'
UPLOAD_LOGENTRY_KEY = 'logs/ds={ds}/{guid}.txt'

class State (enum.Enum):
    XX = 'XX'

    AR = 'AR'
    AZ = 'AZ'
    CA = 'CA'
    CO = 'CO'
    FL = 'FL'
    GA = 'GA'
    IA = 'IA'
    IL = 'IL'
    IN = 'IN'
    KS = 'KS'
    KY = 'KY'
    LA = 'LA'
    MA = 'MA'
    MD = 'MD'
    MI = 'MI'
    MN = 'MN'
    MO = 'MO'
    NC = 'NC'
    NJ = 'NJ'
    NV = 'NV'
    OH = 'OH'
    OK = 'OK'
    OR = 'OR'
    PA = 'PA'
    SC = 'SC'
    TN = 'TN'
    TX = 'TX'
    VA = 'VA'
    WA = 'WA'
    WI = 'WI'

class House (enum.Enum):
    ushouse = 'ushouse'; statesenate = 'statesenate'; statehouse = 'statehouse'

class Incumbency (enum.Enum):
    Open = 'O'
    Democrat = 'D'
    Republican = 'R'

class Storage:
    ''' Wrapper for S3-related details.
    '''
    def __init__(self, s3, bucket, prefix):
        self.s3 = s3
        self.bucket = bucket
        self.prefix = prefix
    
    def to_event(self):
        return dict(bucket=self.bucket, prefix=self.prefix)
    
    @staticmethod
    def from_event(event, s3):
        bucket = event['bucket']
        prefix = event.get('prefix')
        return Storage(s3, bucket, prefix)

class Progress:
    ''' Fraction-like value representing number of completed districts.
    
        Not using fractions.Fraction because it reduces to lowest terms.
    '''
    def __init__(self, completed, expected):
        self.completed = completed
        self.expected = expected
    
    def to_list(self):
        return [self.completed, self.expected]
    
    def to_percentage(self):
        try:
            return '{:.0f}%'.format(100 * self.completed / self.expected)
        except ZeroDivisionError:
            return '???%'
    
    def is_complete(self):
        return bool(self.completed >= self.expected)
    
    def __eq__(self, other):
        return (self.completed / self.expected) == (other.completed / other.expected)

class Model:

    def __init__(self, state:State, house:House, seats:int, incumbency:bool, version:str, key_prefix:str):
        self.state = state
        self.house = house
        self.seats = seats
        self.key_prefix = key_prefix
        self.incumbency = incumbency
        self.version = version
    
    def to_dict(self):
        return dict(
            state = self.state.value,
            house = self.house.value,
            seats = self.seats,
            key_prefix = self.key_prefix,
            incumbency = self.incumbency,
            version = self.version,
            )
    
    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, separators=(',', ':'))
    
    @staticmethod
    def from_dict(data):
        return Model(
            state = State[data['state']],
            house = House[data['house']],
            seats = int(data['seats']),
            key_prefix = str(data['key_prefix']),
            incumbency = bool(data.get('incumbency')),
            version = str(data.get('version', '2017')),
            )
    
    @staticmethod
    def from_json(body):
        return Model.from_dict(json.loads(body))

class Upload:

    def __init__(self, id, key, model:Model=None, districts=None, incumbents=None,
            summary=None, progress=None, start_time=None, message=None,
            description=None, geometry_key=None, status=None, **ignored):
        self.id = id
        self.key = key
        self.model = model
        self.status = status
        self.districts = districts or []
        self.incumbents = incumbents or []
        self.summary = summary or {}
        self.progress = progress
        self.start_time = start_time or time.time()
        self.message = message
        self.description = description
        self.geometry_key = geometry_key
        self.commit_sha = os.environ.get('GIT_COMMIT_SHA')
        
        if not incumbents:
            self.incumbents = [Incumbency.Open.value for i in range(len(self.districts))]
    
    def is_overdue(self):
        return bool(time.time() > (self.start_time + constants.UPLOAD_TIME_LIMIT))
    
    def index_key(self):
        return UPLOAD_INDEX_KEY.format(id=self.id)
    
    def plaintext_key(self):
        return UPLOAD_PLAINTEXT_KEY.format(id=self.id)
    
    def district_key(self, index):
        return UPLOAD_DISTRICTS_KEY.format(id=self.id, index=index)
    
    def logentry_key(self, guid):
        ds = datetime.date.fromtimestamp(self.start_time).strftime('%Y-%m-%d')
        return UPLOAD_LOGENTRY_KEY.format(ds=ds, guid=guid)
    
    def to_plaintext(self):
        ''' Export district totals to a tab-delimited plaintext file
        '''
        sorting_hints = dict({k: i for (i, k) in enumerate((
            'District', 'Democratic Votes', 'Democratic Votes SD',
            'Republican Votes', 'Republican Votes, SD', 'Population 2015',
            'US President 2016 - DEM', 'US President 2016 - REP',
            'US Senate 2016 - DEM', 'US Senate 2016 - REP'))})
        
        has_incumbency = bool(self.model and self.model.incumbency)
        
        try:
            column_names = sorted(self.districts[0]['totals'].keys(),
                key=lambda k: (sorting_hints.get(k, 999), k))
            
            column_names.extend(self.districts[0]['compactness'].keys())
            extra_columns = ['Candidate Scenario'] if has_incumbency else []
                
            out = io.StringIO()
            rows = csv.DictWriter(out,
                ['District'] + extra_columns + column_names, dialect='excel-tab')
            rows.writeheader()
            for (index, district) in enumerate(self.districts):
                totals, compactness = district['totals'], district['compactness']
                extra_values = {'Candidate Scenario': self.incumbents[index]} if has_incumbency else {}
                rows.writerow(dict(District=index+1, **dict(totals, **dict(compactness, **extra_values))))
        
        except Exception as e:
            return f'Error: {e}\n'

        else:
            return out.getvalue()
    
    def to_dict(self):
        progress = self.progress.to_list() if (self.progress is not None) else None

        return dict(
            id = self.id,
            key = self.key,
            model = (self.model.to_dict() if self.model else None),
            status = self.status,
            districts = self.districts,
            incumbents = self.incumbents,
            summary = self.summary,
            progress = progress,
            start_time = self.start_time,
            message = self.message,
            description = self.description,
            geometry_key = self.geometry_key,
            commit_sha = self.commit_sha,
            )
    
    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)
    
    def to_logentry(self):
        ''' Export current plan information to a tab-delimited plaintext file
        '''
        # Important: only append to this list to maintain 
        # backward-compatibility with older entries for PrestoDB
        logentry = [
            # ID string from generate_signed_id()
            self.id,
            
            # Current unix timestamp double
            time.time(),
            
            # Elapsed time in seconds float
            time.time() - self.start_time,
            
            # Text message string
            self.message,
            
            # Model state string
            (self.model.to_dict().get('state') if self.model else None),
            
            # Model house string
            (self.model.to_dict().get('house') if self.model else None),
            
            # Model JSON string
            (self.model.to_json() if self.model else None),
            
            # Upload key string
            self.key,
            
            # Upload status
            {True: 't', False: 'f', None: ''}.get(self.status),
        ]
            
        try:
            out = io.StringIO()
            rows = csv.writer(out, dialect='excel-tab', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            rows.writerow(logentry)
        
        except Exception as e:
            return f'Error: {e}\n'

        else:
            return out.getvalue()
    
    def clone(self, model=None, districts=None, incumbents=None, summary=None, progress=None,
        start_time=None, message=None, description=None, geometry_key=None, status=None):
        return Upload(self.id, self.key,
            model = model or self.model,
            status = status if (self.status is None) else self.status,
            districts = districts or self.districts,
            incumbents = incumbents or self.incumbents,
            summary = summary or self.summary,
            progress = progress if (progress is not None) else self.progress,
            start_time = start_time or self.start_time,
            message = message or self.message,
            description = description or self.description,
            geometry_key = geometry_key or self.geometry_key,
            )
    
    @staticmethod
    def from_dict(data):
        progress = Progress(*data['progress']) if data.get('progress') else None
        model = Model.from_dict(data['model']) if data.get('model') else None
    
        return Upload(
            id = data['id'], 
            key = data['key'],
            model = model,
            status = data.get('status'),
            districts = data.get('districts'),
            incumbents = data.get('incumbents'),
            summary = data.get('summary'),
            progress = progress,
            start_time = data.get('start_time'),
            message = data.get('message'),
            description = data.get('description'),
            geometry_key = data.get('geometry_key'),
            )
    
    @staticmethod
    def from_json(body):
        return Upload.from_dict(json.loads(body))

# Active version of each state model

MODELS2020 = [
    Model(State.XX, House.statehouse,    2,  True, '2020', 'data/XX/006-tilesdir'), # b8e19879
    Model(State.AR, House.ushouse,       4,  True, '2020', 'data/AR/001-tilesdir'), # 6673c68
    Model(State.AR, House.statesenate,  35,  True, '2020', 'data/AR/001-tilesdir'), # 6673c68
    Model(State.AR, House.statehouse,  100,  True, '2020', 'data/AR/001-tilesdir'), # 6673c68
    Model(State.AZ, House.ushouse,       9,  True, '2020', 'data/AZ/002-tilesdir'), # 7a916a4
    Model(State.AZ, House.statesenate,  30,  True, '2020', 'data/AZ/002-tilesdir'), # 7a916a4
    Model(State.AZ, House.statehouse,   60,  True, '2020', 'data/AZ/002-tilesdir'), # 7a916a4
    Model(State.CA, House.ushouse,      55,  True, '2020', 'data/CA/002-tilesdir'), # b969229
    Model(State.CA, House.statesenate,  40,  True, '2020', 'data/CA/002-tilesdir'), # b969229
    Model(State.CA, House.statehouse,   80,  True, '2020', 'data/CA/002-tilesdir'), # b969229
    Model(State.CO, House.ushouse,       7,  True, '2020', 'data/CO/002-tilesdir'), # 57155ad
    Model(State.CO, House.statesenate,  35,  True, '2020', 'data/CO/002-tilesdir'), # 57155ad
    Model(State.CO, House.statehouse,   65,  True, '2020', 'data/CO/002-tilesdir'), # 57155ad
    #Model(State.DE, House.ushouse,        ,  True, '2020', 'data/DE/002-tilesdir'), # 56f7c85
    #Model(State.DE, House.statesenate,    ,  True, '2020', 'data/DE/002-tilesdir'), # 56f7c85
    #Model(State.DE, House.statehouse,     ,  True, '2020', 'data/DE/002-tilesdir'), # 56f7c85
    Model(State.FL, House.ushouse,      27,  True, '2020', 'data/FL/003-tilesdir'), # 56f7c85
    Model(State.FL, House.statesenate,  40,  True, '2020', 'data/FL/003-tilesdir'), # 56f7c85
    Model(State.FL, House.statehouse,  120,  True, '2020', 'data/FL/003-tilesdir'), # 56f7c85
    Model(State.GA, House.ushouse,      14,  True, '2021A', 'data/GA/004-2020'), # 9ab63ed
    Model(State.GA, House.statesenate,  56,  True, '2021A', 'data/GA/004-2020'), # 9ab63ed
    Model(State.GA, House.statehouse,  180,  True, '2021A', 'data/GA/004-2020'), # 9ab63ed
    Model(State.IA, House.ushouse,       4,  True, '2020', 'data/IA/001-tilesdir'), # bcf3dd1
    Model(State.IA, House.statesenate,  50,  True, '2020', 'data/IA/001-tilesdir'), # bcf3dd1
    Model(State.IA, House.statehouse,  100,  True, '2020', 'data/IA/001-tilesdir'), # bcf3dd1
    Model(State.IL, House.ushouse,      18,  True, '2020', 'data/IL/003-tilesdir'), # 56f7c85
    Model(State.IL, House.statesenate,  59,  True, '2020', 'data/IL/003-tilesdir'), # 56f7c85
    Model(State.IL, House.statehouse,  118,  True, '2020', 'data/IL/003-tilesdir'), # 56f7c85
    Model(State.IN, House.ushouse,       9,  True, '2020', 'data/IN/002-tilesdir'), # 45a92e3
    Model(State.IN, House.statesenate,  50,  True, '2020', 'data/IN/002-tilesdir'), # 45a92e3
    Model(State.IN, House.statehouse,  100,  True, '2020', 'data/IN/002-tilesdir'), # 45a92e3
    Model(State.KS, House.ushouse,       5,  True, '2021A', 'data/KS/002-2020'), # 9ab63ed
    Model(State.KS, House.statesenate,  40,  True, '2021A', 'data/KS/002-2020'), # 9ab63ed
    Model(State.KS, House.statehouse,  125,  True, '2021A', 'data/KS/002-2020'), # 9ab63ed
    Model(State.KY, House.ushouse,       6,  True, '2020', 'data/KY/001-tilesdir'), # bcf3dd1
    Model(State.KY, House.statesenate,  38,  True, '2020', 'data/KY/001-tilesdir'), # bcf3dd1
    Model(State.KY, House.statehouse,  100,  True, '2020', 'data/KY/001-tilesdir'), # bcf3dd1
    Model(State.LA, House.ushouse,       6,  True, '2020', 'data/LA/001-tilesdir'), # bcf3dd1
    Model(State.LA, House.statesenate,  39,  True, '2020', 'data/LA/001-tilesdir'), # bcf3dd1
    Model(State.LA, House.statehouse,  105,  True, '2020', 'data/LA/001-tilesdir'), # bcf3dd1
    Model(State.MA, House.ushouse,       9,  True, '2020', 'data/MA/003-tilesdir'), # 56f7c85
    Model(State.MA, House.statesenate,  40,  True, '2020', 'data/MA/003-tilesdir'), # 56f7c85
    Model(State.MA, House.statehouse,  160,  True, '2020', 'data/MA/003-tilesdir'), # 56f7c85
    Model(State.MD, House.ushouse,       8,  True, '2020', 'data/MD/005-tilesdir'), # 56f7c85
    Model(State.MD, House.statesenate,  47,  True, '2020', 'data/MD/005-tilesdir'), # 56f7c85
    Model(State.MD, House.statehouse,   68,  True, '2020', 'data/MD/005-tilesdir'), # 56f7c85
    #Model(State.ME, House.ushouse,        ,  True, '2020', 'data/ME/002-tilesdir'), # 56f7c85
    #Model(State.ME, House.statesenate,    ,  True, '2020', 'data/ME/002-tilesdir'), # 56f7c85
    #Model(State.ME, House.statehouse,     ,  True, '2020', 'data/ME/002-tilesdir'), # 56f7c85
    Model(State.MI, House.ushouse,      14,  True, '2020', 'data/MI/003-tilesdir'), # 56f7c85
    Model(State.MI, House.statesenate,  38,  True, '2020', 'data/MI/003-tilesdir'), # 56f7c85
    Model(State.MI, House.statehouse,  110,  True, '2020', 'data/MI/003-tilesdir'), # 56f7c85
    Model(State.MN, House.ushouse,       8,  True, '2021A', 'data/MN/003-2020'), # 9ab63ed
    Model(State.MN, House.statesenate,  67,  True, '2021A', 'data/MN/003-2020'), # 9ab63ed
    Model(State.MN, House.statehouse,  134,  True, '2021A', 'data/MN/003-2020'), # 9ab63ed
    Model(State.MO, House.ushouse,       8,  True, '2020', 'data/MO/002-tilesdir'), # 9f98656
    Model(State.MO, House.statesenate,  34,  True, '2020', 'data/MO/002-tilesdir'), # 9f98656
    Model(State.MO, House.statehouse,  163,  True, '2020', 'data/MO/002-tilesdir'), # 9f98656
    #Model(State.MT, House.ushouse,        ,  True, '2020', 'data/MT/002-tilesdir'), # 56f7c85
    #Model(State.MT, House.statesenate,    ,  True, '2020', 'data/MT/002-tilesdir'), # 56f7c85
    #Model(State.MT, House.statehouse,     ,  True, '2020', 'data/MT/002-tilesdir'), # 56f7c85
    Model(State.NC, House.ushouse,      13,  True, '2020', 'data/NC/015-tilesdir'), # 56f7c85
    Model(State.NC, House.statesenate,  50,  True, '2020', 'data/NC/015-tilesdir'), # 56f7c85
    Model(State.NC, House.statehouse,  120,  True, '2020', 'data/NC/015-tilesdir'), # 56f7c85
    #Model(State.ND, House.ushouse,        ,  True, '2020', 'data/ND/002-tilesdir'), # 56f7c85
    #Model(State.ND, House.statesenate,    ,  True, '2020', 'data/ND/002-tilesdir'), # 56f7c85
    #Model(State.ND, House.statehouse,     ,  True, '2020', 'data/ND/002-tilesdir'), # 56f7c85
    #Model(State.NH, House.ushouse,        ,  True, '2020', 'data/NH/002-tilesdir'), # 56f7c85
    #Model(State.NH, House.statesenate,    ,  True, '2020', 'data/NH/002-tilesdir'), # 56f7c85
    #Model(State.NH, House.statehouse,     ,  True, '2020', 'data/NH/002-tilesdir'), # 56f7c85
    Model(State.NJ, House.ushouse,      12,  True, '2020', 'data/NJ/001-tilesdir'), # bcf3dd1
    Model(State.NJ, House.statesenate,  40,  True, '2020', 'data/NJ/001-tilesdir'), # bcf3dd1
    Model(State.NJ, House.statehouse,   80,  True, '2020', 'data/NJ/001-tilesdir'), # bcf3dd1
    Model(State.NV, House.ushouse,       4,  True, '2020', 'data/NV/001-tilesdir'), # bcf3dd1
    Model(State.NV, House.statesenate,  21,  True, '2020', 'data/NV/001-tilesdir'), # bcf3dd1
    Model(State.NV, House.statehouse,   42,  True, '2020', 'data/NV/001-tilesdir'), # bcf3dd1
    Model(State.OH, House.ushouse,      16,  True, '2021A', 'data/OH/001-2020'), # 9ab63ed
    Model(State.OH, House.statesenate,  33,  True, '2021A', 'data/OH/001-2020'), # 9ab63ed
    Model(State.OH, House.statehouse,   99,  True, '2021A', 'data/OH/001-2020'), # 9ab63ed
    Model(State.OK, House.ushouse,       5,  True, '2020', 'data/OK/001-tilesdir'), # 49ac5ef
    Model(State.OK, House.statesenate,  48,  True, '2020', 'data/OK/001-tilesdir'), # 49ac5ef
    Model(State.OK, House.statehouse,  101,  True, '2020', 'data/OK/001-tilesdir'), # 49ac5ef
    Model(State.OR, House.ushouse,       5,  True, '2020', 'data/OR/002-tilesdir'), # 57155ad
    Model(State.OR, House.statesenate,  30,  True, '2020', 'data/OR/002-tilesdir'), # 57155ad
    Model(State.OR, House.statehouse,   60,  True, '2020', 'data/OR/002-tilesdir'), # 57155ad
    Model(State.PA, House.ushouse,      18,  True, '2020', 'data/PA/010-tilesdir'), # d9fcd35
    Model(State.PA, House.statesenate,  50,  True, '2020', 'data/PA/010-tilesdir'), # d9fcd35
    Model(State.PA, House.statehouse,  203,  True, '2020', 'data/PA/010-tilesdir'), # d9fcd35
    #Model(State.RI, House.ushouse,        ,  True, '2020', 'data/RI/002-tilesdir'), # 56f7c85
    #Model(State.RI, House.statesenate,    ,  True, '2020', 'data/RI/002-tilesdir'), # 56f7c85
    #Model(State.RI, House.statehouse,     ,  True, '2020', 'data/RI/002-tilesdir'), # 56f7c85
    Model(State.SC, House.ushouse,       7,  True, '2020', 'data/SC/001-tilesdir'), # bcf3dd1
    Model(State.SC, House.statesenate,  46,  True, '2020', 'data/SC/001-tilesdir'), # bcf3dd1
    Model(State.SC, House.statehouse,  124,  True, '2020', 'data/SC/001-tilesdir'), # bcf3dd1
    #Model(State.SD, House.ushouse,        ,  True, '2020', 'data/SD/002-tilesdir'), # 56f7c85
    #Model(State.SD, House.statesenate,    ,  True, '2020', 'data/SD/002-tilesdir'), # 56f7c85
    #Model(State.SD, House.statehouse,     ,  True, '2020', 'data/SD/002-tilesdir'), # 56f7c85
    Model(State.TN, House.ushouse,       9,  True, '2020', 'data/TN/003-tilesdir'), # 56f7c85
    Model(State.TN, House.statesenate,  33,  True, '2020', 'data/TN/003-tilesdir'), # 56f7c85
    Model(State.TN, House.statehouse,   99,  True, '2020', 'data/TN/003-tilesdir'), # 56f7c85
    Model(State.TX, House.ushouse,      36,  True, '2020', 'data/TX/003-tilesdir'), # 56f7c85
    Model(State.TX, House.statesenate,  31,  True, '2020', 'data/TX/003-tilesdir'), # 56f7c85
    Model(State.TX, House.statehouse,  150,  True, '2020', 'data/TX/003-tilesdir'), # 56f7c85
    Model(State.VA, House.ushouse,      11,  True, '2020', 'data/VA/003-tilesdir'), # 08df871
    Model(State.VA, House.statesenate,  40,  True, '2020', 'data/VA/003-tilesdir'), # 08df871
    Model(State.VA, House.statehouse,  100,  True, '2020', 'data/VA/003-tilesdir'), # 08df871
    #Model(State.VT, House.ushouse,        ,  True, '2020', 'data/VT/002-tilesdir'), # 56f7c85
    #Model(State.VT, House.statesenate,    ,  True, '2020', 'data/VT/002-tilesdir'), # 56f7c85
    #Model(State.VT, House.statehouse,     ,  True, '2020', 'data/VT/002-tilesdir'), # 56f7c85
    Model(State.WA, House.ushouse,      10,  True, '2020', 'data/WA/002-tilesdir'), # 57155ad
    Model(State.WA, House.statesenate,  49,  True, '2020', 'data/WA/002-tilesdir'), # 57155ad
    Model(State.WA, House.statehouse,   98,  True, '2020', 'data/WA/002-tilesdir'), # 57155ad
    Model(State.WI, House.ushouse,       8,  True, '2020', 'data/WI/007-tilesdir'), # 56f7c85
    Model(State.WI, House.statesenate,  33,  True, '2020', 'data/WI/007-tilesdir'), # 56f7c85
    Model(State.WI, House.statehouse,   99,  True, '2020', 'data/WI/007-tilesdir'), # 56f7c85
    #Model(State.WY, House.ushouse,        ,  True, '2020', 'data/WY/002-tilesdir'), # 56f7c85
    #Model(State.WY, House.statesenate,    ,  True, '2020', 'data/WY/002-tilesdir'), # 56f7c85
    #Model(State.WY, House.statehouse,     ,  True, '2020', 'data/WY/002-tilesdir'), # 56f7c85
    ]
