# -*- coding:utf8-*-

"""
超值买返商品
  @pageId	Integer	必须	分页id：常规分页方式，请直接传入对应页码（比如：1,2,3……）
  @pageSize	Integer	必须	每页条数，默认20，最大100条
  @sort	Integer	必须	排序方式：1-返得红包百分比升序2-返得红包百分比降序3-销量降序4-销量升序5-返得红包金额升序6-返得红包金额降序
"""
from dtkApi.apiRequest import Request


class CzmfGoodsListReq(Request):
    url = 'goods/activity/list-goods-czmf'
    check_params = ['pageId','pageSize','sort']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pageId, pageSize,sort):
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
        self.addParams('sort', sort)
