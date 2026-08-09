# -*- coding:utf8-*-

"""
淘口令解析
@content  String 必须 包含淘口令的文本。 若文本中有多个淘口令，仅解析第一个。（目前仅支持商品口令和二合一券口令）
"""
from dtkApi.apiRequest import Request


class ParseTaokoulingReq(Request):
    url = 'tb-service/parse-taokouling'
    check_params = ['content']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, content):
        self.addParams('content', content)
