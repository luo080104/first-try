# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
京东链接解析
 @url String 必须  京东链接地址，内容URLEncode后使用
"""


class JdUrlParseReq(Request):
    url = 'dels/jd/kit/parseUrl'
    check_params = ['url']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, url):
        self.addParams('url', url)