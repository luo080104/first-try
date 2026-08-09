# -*- coding:utf8-*-

"""
淘系订单查询
 @queryType Number	必须	查询时间类型，1：按照订单淘客创建时间查询，2:按照订单淘客付款时间查询，3:按照订单淘客结算时间查询，4：按照订单更新时间（5.27新增字段）
 @positionIndex	String	非必须	位点，第一页数据返回里面有个这个字段，查第二页的数据的时候就传过去
 @pageSize	Number	非必须	页大小，默认20，1~100
 @memberType	Number	非必须	推广者角色类型,2:二方，3:三方，不传，表示所有角色
 @tkStatus	Number	非必须	淘客订单状态，12-付款，13-关闭，14-确认收货，3-结算成功;不传，表示所有状态
 @endTime	String	必须	订单查询结束时间，订单开始时间至订单结束时间，中间时间段日常要求不超过3个小时，但如618、双11、年货节等大促期间预估时间段不可超过20分钟，超过会提示错误，调用时请务必注意时间段的选择，以保证亲能正常调用！ 时间格式：YYYY-MM-DD HH:MM:SS
 @startTime	String	必须	订单查询开始时间。时间格式：YYYY-MM-DD HH:MM:SS
 @jumpType	Number	非必须	跳转类型，当向前或者向后翻页必须提供,-1: 向前翻页,1：向后翻页
 @pageNo	Number	非必须	第几页，默认1，1~100
 @orderScene	Number	非必须	场景订单场景类型，1:常规订单，2:渠道订单，3:会员运营订单，默认为1
 @authId Number 非必须 在平台的淘宝授权id(https://www.dataoke.com/shouquan)，如果传入了该参数则必须填写对应淘宝联盟授权账号的pid
 @pid String 非必须 推广位ID，如果传入了authId则必须填写对应淘宝联盟授权账号的pi
"""

from dtkApi.apiRequest import Request


class OrderDetailsReq(Request):
    url = 'tb-service/get-order-details'
    check_params = ['queryType','endTime','startTime']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self,
                  queryType, endTime, startTime, positionIndex = None, pageSize = None, memberType = None, tkStatus = None,
                  jumpType = None, pageNo = None, orderScene = None, authId=None, pid=None):
        self.addParams('queryType', queryType)
        self.addParams('positionIndex', positionIndex)
        self.addParams('pageSize', pageSize)
        self.addParams('memberType', memberType)
        self.addParams('tkStatus', tkStatus)
        self.addParams('endTime', endTime)
        self.addParams('startTime', startTime)
        self.addParams('jumpType', jumpType)
        self.addParams('pageNo', pageNo)
        self.addParams('orderScene', orderScene)
        self.addParams('authId', authId)
        self.addParams('pid', pid)

