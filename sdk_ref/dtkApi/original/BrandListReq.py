# -*- coding:utf8-*-

"""
品牌库
@pageId String 必须 页码
@pageSize Number 非必须 每页条数，默认为20，最大值100
"""
from dtkApi.apiRequest import Request


class BrandListReq(Request):
    url = 'tb-service/get-brand-list'
    check_params = ['pageId']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pageId, pageSize=None):
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
