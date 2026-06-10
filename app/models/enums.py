import enum

class RequestSource(str, enum.Enum):
    EMAIL = 'EMAIL'
    UPLOAD = 'UPLOAD'

class RequestStatus(str, enum.Enum): 
    RECEIVED = 'RECEIVED'
    PARSING = 'PARSING'
    PARSE_ERROR = 'PARSE_ERROR'
    SEARCHING = 'SEARCHING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'


class ItemStatus(str, enum.Enum): 
    PENDING = 'PENDING'
    SEARCHING = 'SEARCHING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    PARTIAL = 'PARTIAL'
    NO_RESULTS = 'NO_RESULTS'    


class ParseMethod(str, enum.Enum):
    TEMPLATE_XLSX = 'TEMPLATE_XLSX'
    TEMPLATE_CSV = 'TEMPLATE_CSV'
    EMAIL_TABLE = 'EMAIL_TABLE'
    LLM_FALLBACK = 'LLM_FALLBACK'

