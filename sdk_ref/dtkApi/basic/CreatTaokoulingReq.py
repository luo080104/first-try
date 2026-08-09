
# -*- coding:utf8-*-
"""
淘口令生成
text string  必须 口令弹框内容，长度大于5个字符
url string 必须 口令跳转目标页，如：https://uland.taobao.com/，必须以https开头，可以是二合一链接、长链接、短链接等各种淘宝高佣链接；支持渠道备案链接。* 该参数需要进行Urlencode编码后传入*
logo string 非必须 	口令弹框logoURL
userId string 非必须 生成口令的淘宝用户ID，非必传参数
"""
from dtkApi.apiRequest import Request

class CreatTaokoulingReq(Request):
    url='tb-service/creat-taokouling'
    check_params=['text','url']
    #GET请求
    def getResponse(self):
        if self.check_args(self.params,self.check_params):
            return self.request('GET',api_url=self.url,args=self.params)

    def setParams(self,text,url, logo=None, userId=None):
        self.addParams('text', text)
        self.addParams('url', url)
        self.addParams('logo', logo)
        self.addParams('userId', userId)