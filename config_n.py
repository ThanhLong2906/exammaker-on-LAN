import os
class Config:
    SECRET_KEY = os.urandom(24)
    MYSQL_HOST = "localhost"
    MYSQL_USER = "root"
    MYSQL_PASSWORD = "1234"
    MYSQL_DB = "exam_system"
    MYSQL_CURSORCLASS = "DictCursor"