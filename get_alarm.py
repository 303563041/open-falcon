#!/usr/bin/python

import redis
import logging
import time
import requests
import json

# set log format
logger = logging.getLogger("Townkins")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("./alarm.log")
logger.addHandler(file_handler)

# constants for duty api
DUTY_API = "http://duty.funplus.io/Event/index"
DUTY_SPACE_UUID = "xxxxxxxxxxx"
DUTY_TOKEN = "xxxxxxxxxxxxxxxxx"
DUTY_CATEGORY = "monitor"
#DUTY_DEFAULT_STATUS = 2  # 2 stands for critical
d = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def conn():
    '''
    set redis conn
    '''
    try:
        pool = redis.ConnectionPool(host='localhost', port=6379, decode_responses=True)
        r = redis.Redis(connection_pool=pool)
    except Exception,e:
        logger.error("%s Fail to connection redis: %s" % (d, e))
    return r

def call_duty(html_str, service, tags, status,
              space_uuid=DUTY_SPACE_UUID, token=DUTY_TOKEN, category=DUTY_CATEGORY):
    data = {
        "space_uuid": space_uuid,
        "token": token,
        "category": category,
        "status": status,
        "service": service,
        "tags": tags,
        "checktime": time.time(),
        "message": html_str
    }
    flag = False
    for i in range(3):
        try:
            if not flag:
                rs = requests.post(DUTY_API, data=data)
                logger.info("%s Call duty succeed!" % d)
                logger.info("%s %s" % (d, data))
                flag = True
        except Exception, e:
            logger.error("%s Failed to call duty api: %s" % (d, e.message))
            flag = False
    return flag

def format_msg(info):
    ''' Format the log information. '''
    tg = ""
    for k, v in info["strategy"]["tags"].items():
        tg += "%s=%s," % (k, v)
    msg = "Expr(%s/%s, %s%s%s); the %s/%s current value is %s; This event has lasted %s time" % (info["strategy"]["metric"], tg.strip(','), info["strategy"]["func"], info["strategy"]["operator"], info["strategy"]["rightValue"], info["strategy"]["metric"], tg.strip(','), info["leftValue"], info["currentStep"])
    service = info["strategy"]["metric"]
    tags = "townkins:%s" % info["endpoint"]
    return msg, tags, service


def main():
    '''
    get all keys for alarm info
    '''
    r = conn()
    keys = r.keys()
    if keys:
        for key in keys:
            if r.type(key) == "list":
                for value in r.lrange(key, 0, -1):
                    info = json.loads(value)
                    if info["status"] == "PROBLEM":
                        status = 2
                        msg, tags, service = format_msg(info)

                        # send alarm error msg to duty
                        flag = call_duty(msg, service, tags, status)

                        # del error msg
                        if flag:
                            r.lrem(key, value, 1)
                            logger.info("%s del Problem alarm msg, key: %s, value: %s" % (d, key, value))

                    elif info["status"] == "OK":
                        status = 0
                        msg, tags, service = format_msg(info)
                        # send alarm OK msg to duty
                        flag = call_duty(msg, service, tags, status)

                        # del ok msg
                        if flag:
                            r.lrem(key, value, 1)
                            logger.info("%s del OK alarm msg, key: %s, value: %s" % (d, key, value))
    else:
        logger.info("%s no alarm" % d)




if __name__ == "__main__":
    main()
