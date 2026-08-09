# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
京东一元购订单查询
  @orderTimeType	String	必须	订单时间类型：(1：下单时间，2：完成时间（购买用户确认收货时间），3：更新时间
  @startTime	String	必须	开始时间 格式yyyy-MM-dd HH:mm:ss，与endTime间隔不超过30天
  @endTime	String	必须	结束时间 格式yyyy-MM-dd HH:mm:ss，与startTime间隔不超过30天
  @pageId	String	非必须	分页id，默认为1，支持scroll翻页查询
  @pageSize	Integer	非必须	每页记录条数，最大支持200
  @code	String	非必须	自定义标识，用于区分下游推广渠道（如果没有做代理返利模式，可不传）


"""


class JdOneDollarPurchaseOrderInquiryReq(Request):
    url = 'dels/jd/order/outer/get-order-list'
    check_params = ['orderTimeType','startTime','endTime']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, orderTimeType, startTime, endTime, pageId=None, pageSize=None, code=None):
        self.addParams('orderTimeType', orderTimeType)
        self.addParams('startTime', startTime)
        self.addParams('endTime', endTime)
        self.addParams('pageId', pageId)
        self.addParams('pageSize', pageSize)
        self.addParams('code', code)

