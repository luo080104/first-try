# -*- coding:utf8-*-

"""
高效转链
 @goodsId	String	必须	淘宝商品id
 @couponId	String	非必须	商品的优惠券ID，一个商品在联盟可能有多个优惠券，可通过填写该参数的方式选择使用的优惠券，请确认优惠券ID正确，否则无法正常跳转
 @pid	string	非必须	推广位ID，用户可自由填写当前大淘客账号下已授权淘宝账号的任一pid，若未填写，则默认使用创建应用时绑定的pid
 @channelId	string	非必须	渠道id将会和传入的pid进行验证，验证通过将正常转链，请确认填入的渠道id是正确的 channelId对应联盟的relationId
 @rebateType	Number	非必须	付定返红包，0.不使用付定返红包，1.参与付定返红包
 @specialId	string	非必须	会员运营id
 @externalId	string	非必须	淘宝客外部用户标记，如自身系统账户ID；微信ID等
 @xid	string	非必须	团长与下游渠道合作的特殊标识，用于统计渠道推广效果 （新增入参）
 @leftSymbol	string	非必须	淘口令左边自定义符号,默认￥ （2021/3/9新增入参）
 @rightSymbol	string	非必须	淘口令右边自定义符号,默认￥ （2021/3/9新增入参）

"""
from dtkApi.apiRequest import Request


class PrivilegeLinkReq(Request):
    url = 'tb-service/get-privilege-link'
    check_params = ['goodsId']

    # GET请求
    def getResponse(self):
        if self.check_args(self.params, self.check_params):
            return self.request('GET', api_url=self.url, args=self.params)

    def setParams(self, goodsId, couponId=None, pid=None, channelId=None, rebateType=None, specialId=None,
                  externalId=None, xid=None, leftSymbol=None, rightSymbol=None):
        self.addParams('goodsId', goodsId)
        self.addParams('couponId', couponId)
        self.addParams('pid', pid)
        self.addParams('channelId', channelId)
        self.addParams('rebateType', rebateType)
        self.addParams('specialId', specialId)
        self.addParams('externalId', externalId)
        self.addParams('xid', xid)
        self.addParams('leftSymbol', leftSymbol)
        self.addParams('rightSymbol', rightSymbol)
