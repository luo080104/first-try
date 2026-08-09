# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
商品精推素材
 @id String 必须  淘宝商品id
"""


class GoodsMaterialListReq(Request):
    url = 'goods/material/list'
    check_params = ['id']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, id):
        self.addParams('id', id)
