# -*- coding:utf8-*-

"""
热门主播力荐商品
  @pageId	String	必须	分页id：常规分页方式，请直接传入对应页码（比如：1,2,3……）
  @pageSize	Integer	必须	每页返回条数，每页条数支持输入10,20，50

"""
from dtkApi.apiRequest import Request


class PopularAnchorCommendReq(Request):
    url = 'live/goods-list'
    check_params = ['pageId','pageSize']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self,pageId, pageSize):
        self.addParams('pageSize', pageSize)
        self.addParams('pageId', pageId)
