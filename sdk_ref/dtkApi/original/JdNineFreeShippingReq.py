# -*- coding:utf8-*-
"""
京东9.9元包邮
  @pageId	Integer	非必须	页码（默认为1）
  pageSize	Integer	非必须	每页记录条数（默认20）
  sort	Integer	必须	排序：0-综合排序；1-价格升序；2-价格降序
"""
from dtkApi.apiRequest import Request


class JdNineFreeShippingReq(Request):
    url = 'dels/jd/column/list-nines'
    check_params = ['sort']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, sort,pageId=None, pageSize=None):
        self.addParams('pageSize', pageSize)
        self.addParams('pageId', pageId)
        self.addParams('sort', sort)
