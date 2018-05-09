class Config:
    DEBUG = False
    TESTING = False
    POSTGRES_USER = "thesaurus"
    POSTGRES_PW = "thesaurus"
    POSTGRES_URL = "127.0.0.1:5432"
    POSTGRES_DB = "thesaurus"
    DB_URI = 'postgresql+psycopg2://{user}:{pw}@{url}/{db}'.format(
        user=POSTGRES_USER,
        pw=POSTGRES_PW,
        url=POSTGRES_URL,
        db=POSTGRES_DB
    )
    IDENTIFIER = 'thesaurus'
    LANGUAGE_CODE = 'en'
    PER_PAGE = 25
    ELASTICSEARCH_URI = "http://127.0.0.1:9200/"
    INDEX_NAME = 'thesaurus'
    REDIS_HOST = 'localhost'
    REDIS_PORT = "6379"
    REDIS_DB = 0
    REDIS_TIMEOUT = 30


class ProductionConfig(Config):
    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True


class AWSConfig(Config):
    DEBUG = True
