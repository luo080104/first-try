# -*- coding:utf8-*-

"""
热搜榜
"""
from dtkApi.apiRequest import Request


class ListHotWordsReq(Request):
    url = 'etc/search/list-hot-words'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self):
        pass
