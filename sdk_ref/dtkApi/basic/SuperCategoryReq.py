# -*- coding:utf8-*-

"""
超级分类

"""
from dtkApi.apiRequest import Request


class SuperCategoryReq(Request):
    url = 'category/get-super-category'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self):
        pass