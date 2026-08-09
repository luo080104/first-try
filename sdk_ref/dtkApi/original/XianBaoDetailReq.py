# -*- coding:utf8-*-
"""
线报
  @topic	Integer	非必须	类型：1淘宝商品2天猫商品3猫超商品4店铺5会场6优惠券7京东商
  @type	Integer	非必须	分类：1淘宝好价，2天猫超市，3京东好价
  @pageId	Integer	非必须	页码，默认为1
  @pageSize	Integer	非必须	每页记录数，默认20
  @selectTime	Long	非必须	rush-整点抢购时的时间戳（秒），示例：1617026400


"""
from dtkApi.apiRequest import Request


class XianBaoDetailReq(Request):
    url = 'dels/spider/list-tip-off'
    check_params = []

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, topic=None, type=None, pageId=None, pageSize=None, selectTime=None):
        self.addParams('topic', topic)
        self.addParams('type', type)
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
        self.addParams('selectTime', selectTime)
