# -*- coding:utf8-*-

"""
淘系万能解析
@content String 必须 包含淘口令、链接的文本。优先解析淘口令，再按序解析每个链接，直至解出有效信息。如果淘口令失效或者不支持的类型的情况，会按顺序解析链接。如果存在解析失败，请再试一次
"""
from dtkApi.apiRequest import Request


class ParseContentReq(Request):
    url = 'tb-service/parse-content'
    check_params = ['content']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, content):
        self.addParams('content', content)
