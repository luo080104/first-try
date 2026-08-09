# -*- coding:utf8-*-
"""
专辑列表
  @pageId	String	非必须	默认为1，支持scroll查询
  @pageSize	Integer	非必须	每页记录条数：10，20，50，100
  @albumType	Integer	必须	专辑类型：0-全部，1-官方精选，2-创作者
  @sort	Integer	非必须	排序方式，0-默认排序；1-按推广量降序排列

"""
from dtkApi.apiRequest import Request


class AlbumListReq(Request):
    url = 'album/album-list'
    check_params = ['albumType']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self,albumType, pageId=None, pageSize=None, sort=None):
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
        self.addParams('albumType', albumType)
        self.addParams('sort', sort)