# -*- coding:utf8-*-
"""
官方活动(1元购)
  pageId	String	 必须	分页id，支持传统的页码分页方式
  pageSize	Number	非必须	每页条数，默认为20
  type	Number	非必须	输出的端口类型：0.全部（默认），1.PC，2.无线
  channelID	Number	非必须	阿里妈妈上申请的渠道id
"""
from dtkApi.apiRequest import Request


class TbTopicListReq(Request):
    url = 'category/get-tb-topic-list'
    check_params = ['pageId']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, pageId, pageSize=None,type=None,channelID=None):
        self.addParams('pageSize', pageSize)
        self.addParams('pageId', pageId)
        self.addParams('type', type)
        self.addParams('channelID', channelID)
