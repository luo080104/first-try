# -*- coding:utf8-*-

"""
猜你喜欢
  @id Number 必须 大淘客的商品id
  @size Number 非必须 每页条数，默认10 ， 最大值100
"""
from dtkApi.apiRequest import Request


class ListSimilerGoodsByOpenReq(Request):
    url = 'goods/list-similer-goods-by-open'
    check_params = ['id']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self,id, size=None):
        self.addParams('size', size)
        self.addParams('id', id)