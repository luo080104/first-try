# -*- coding:utf8-*-
from dtkApi.apiRequest import Request

"""
淘宝商品
淘礼金创建
 @alimamaAppKey	String	必须	请填写您申请的具有淘礼金应用权限的Appkey 申请地址https://survey.taobao.com/apps/zhiliao/BQ2RPRlpU
 @alimamaAppSecret	String	必须	请填写您申请的具有淘礼金应用权限的Appsecret
 @name	String	必须	淘礼金名称，最大10个字符
 @itemId	String	必须	宝贝商品id
 @pid	String	非必须	联盟应用对应的pid
 @campaignType	Integer	非必须	佣金计划类型1-定向（DX）；2-鹊桥（LINK_EVENT）；3-营销（MKT）
 @perFace	String	必须	单个淘礼金面额，支持两位小数，单位元
 @totalNum	Integer	必须	淘礼金总个数
 @winNumLimit	Integer	必须	单用户累计中奖次数上限，最小值为1
 @sendStartTime	String	必须	发放开始时间，格式为yyyy-MM-dd HH:mm:ss示例：发放开始时间 2018-09-01 00:00:00
 @sendEndTime	String	必须	发放截止时间，格式为yyyy-MM-dd HH:mm:ss发放截止时间，示例： 2018-09-01 00:00:00
 @useEndTimeMode	String	非必须	结束日期的模式,1:相对时间，2:绝对时间使用结束日期。如果是结束时间模式为相对时间，时间格式为1-7直接的整数,例如，1（相对领取时间1天）； 如果是绝对时间，格式为yyyy-MM-dd，例如，2019-01-29，表示到2019-01-29 23:59:59结束
 @useStartTime	String	非必须	使用开始日期。相对时间，无需填写，以用户领取时间作为使用开始时间。绝对时间，格式 yyyy-MM-dd，例如，2019-01-29，表示从2019-01-29 00:00:00 开始
 @userEndTime	String	非必须	使用结束日期。如果是结束时间模式为相对时间，时间格式为1-7直接的整数,例如，1（相对领取时间1天）； 如果是绝对时间，格式为yyyy-MM-dd，例如，2019-01-29，表示到2019-01-29 23:59:59结束
"""


class TbCashGiftCreateReq(Request):
    url = 'dels/taobao/kit/create-tlj'
    check_params = ['alimamaAppKey','alimamaAppSecret','name','itemId','perFace','totalNum','winNumLimit','sendStartTime','sendEndTime']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, alimamaAppKey, alimamaAppSecret, name, itemId,winNumLimit,perFace, totalNum, sendStartTime,
                  sendEndTime, pid=None, campaignType=None,  useEndTimeMode=None, useStartTime=None, userEndTime=None):
        self.addParams('alimamaAppKey', alimamaAppKey)
        self.addParams('alimamaAppSecret', alimamaAppSecret)
        self.addParams('name', name)
        self.addParams('itemId', itemId)
        self.addParams('pid', pid)
        self.addParams('campaignType', campaignType)
        self.addParams('perFace', perFace)
        self.addParams('totalNum', totalNum)
        self.addParams('winNumLimit', winNumLimit)
        self.addParams('sendStartTime', sendStartTime)
        self.addParams('sendEndTime', sendEndTime)
        self.addParams('useEndTimeMode', useEndTimeMode)
        self.addParams('useStartTime', useStartTime)
        self.addParams('userEndTime', userEndTime)
