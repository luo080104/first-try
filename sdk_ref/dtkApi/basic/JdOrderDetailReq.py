# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
京东订单查询
 @pageNo Integer 非必须  页码（默认为1）
 @pageSize 	Integer	非必须	每页记录条数，默认100
 @type	Integer	必须	订单时间查询类型(1：下单时间，2：完成时间（购买用户确认收货时间），3：更新时间
 @childUnionId	Long	非必须	子推客unionID，传入该值可查询子推客的订单，注意不可和key同时传入。（需联系运营开通PID权限才能拿到数据）
 @key	String	必须	工具商传入推客的授权key，可帮助该推客查询订单，注意不可和childUnionid同时传入。（需联系运营开通工具商权限才能拿到数据，请在京东联盟->我的工具->我的API->领取授权KEY中获取key）
 @startTime	String	必须	开始时间 格式yyyy-MM-dd HH:mm:ss，与endTime间隔不超过1小时
 @endTime	String	必须	结束时间 格式yyyy-MM-dd HH:mm:ss，与startTime间隔不超过1小时
 @fields	String	非必须	支持出参数据筛选，逗号分隔，目前可用：goodsInfo（商品信息）,categoryInfo(类目信息）

"""


class JdOrderDetailReq(Request):
    url = 'dels/jd/order/get-official-order-list'
    check_params = ['type','key','startTime','endTime']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, type,key,startTime, endTime,pageNo=None, pageSize=None, childUnionId=None, fields=None):
        self.addParams('pageNo', pageNo)
        self.addParams('pageSize', pageSize)
        self.addParams('type', type)
        self.addParams('childUnionId', childUnionId)
        self.addParams('key', key)
        self.addParams('startTime', startTime)
        self.addParams('endTime', endTime)
        self.addParams('fields', fields)
