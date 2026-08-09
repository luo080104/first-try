# -*- coding:utf8-*-
"""
京东实时榜单
  @pageId	Integer	非必须	页码（默认为1）
  pageSize	Integer	非必须	每页记录条数（默认20）
"""
from dtkApi.apiRequest import Request


class JdRealTimeListReq(Request):
    url = 'dels/jd/column/list-real-ranks'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self,pageId=None, pageSize=None):
        self.addParams('pageSize', pageSize)
        self.addParams('pageId', pageId)
