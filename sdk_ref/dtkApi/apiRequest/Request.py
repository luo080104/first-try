# -*- coding:utf8 -*-
import operator
import hashlib
import copy
import subprocess
import logging
import time
import random

logging.captureWarnings(True)
try:
    import requests
except:
    print('尚未安装requests库，正在安装，请稍后！')
    subprocess.call('pip install requests')
    print('requests库安装成功！第一次调用接口！')
    import requests
class Request():
    #将公共参数 初始化
    def __init__(self,appKey,appSecret,apiVersion):
        self.appKey=appKey
        self.appSecret=appSecret
        self.apiVersion=apiVersion
        self.params={}

    def md5(self,arg):
        md5 = hashlib.md5()
        loc_bytes_utf8 = arg.encode(encoding="utf-8")
        md5.update(loc_bytes_utf8)
        return md5.hexdigest()
    """#key 加密算法 
    1：对传入的产生 按照key 进行排序
    2：将排序后的数据 将各数据字段 用字符串 ‘&’连接起来
    如：data={appkey:123,pageId:1} 处理后 appkey=123&pageId=1
    3:在处理后的数据字符串后追加 appSecret  如 appSecret=helloworld 则 最终 加密字符串为appkey=123&pageId=1&key=hellworld
    4：采用MD5加密算法对 处理后的字符串进行加密
    """

    def md5_sign(self,args=None):
        copy_args =copy.deepcopy(args)
        timer = int(time.time() * 1000)
        nonce = random.randint(100000, 999999)
        sign = self.md5('appKey='+self.appKey+'&timer='+str(timer)+'&nonce='+str(nonce)+'&key='+self.appSecret).upper()
        copy_args['signRan'] = sign
        copy_args['timer'] = timer
        copy_args['nonce'] = nonce
        return copy_args
    def check_args(self,arg,check_params):
        params=copy.deepcopy(check_params)
        if arg:
            if len(check_params)>0:
                for key in  check_params:
                    if key in arg.keys():
                        params.remove(key)
                # print(self.__class__.check_parmas,list(arg.keys()))
                # print(i)
                if len(params)==0:
                    return True
                else:
                    print("请传入必要参数%s且不能为空"%str(params))
                    return  False
            else:
                return  True
        else:
            if len(check_params)>0:
                print("请传入必要参数%s且不能为空"%str(check_params))
                return False
            else:
                return True
    #设置传入参数
    def addParams(self,key,value):
        if value:
            self.params[key]=value
    def request(self,method,api_url,args,UserAgent=None,ContentType=None):
        url="https://openapi.dataoke.com/api/"+api_url
        if UserAgent == None:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.84 Safari/537.36",
                       'Content-Type':ContentType,
                       'Client-Sdk-Type':'python'}
        else:
            headers = {"User-Agent": UserAgent,'Content-Type': ContentType,'Client-Sdk-Type':'python'}
        # 将appkey 加入 待排序
        args['appKey']=self.appKey
        #将apiVersion 加入
        args['version']=self.apiVersion
        #生成签名
        data = self.md5_sign(args=args)
        # print(data)
        method_tmp = method.lower()
        if method_tmp == 'get':
            response = requests.request(method=method_tmp,url=url,params=data,headers=headers,verify=False).json()
            return response
        elif method_tmp == 'post':
            response = requests.request(method=method_tmp,url=url,data=data,headers=headers,verify=False).json()
            return response



