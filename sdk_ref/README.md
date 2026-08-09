# openapi-sdk-python

#### 介绍
大淘客开放平台SDK PYTHON版

该sdk 包含如下接口:

###### `大淘客开放平台--基础工具API`
`ActivityLinkReq:官方活动会场转链`
`CreatTaokoulingReq:淘口令生成`
`FirstOrderGiftMoneyReq:首单礼金`
`OrderDetailsReq:淘系订单查询`
`ParseContentReq:淘系万能解析`
`ParseTaokoulingReq:淘口令解析`
`PrivilegeLinkReq:高效转链`
`SuperCategoryReq:超级分类`
`CollectionListReq:我的收藏`
`JdGoodsLinkReq:京东商品转链`
`TwdToTwdReq:淘口令转淘口令`
`ShearPlateDistinguishReq:剪切板识别`
`MergeRedEnvelopesReq:三合一红包`
`JdOneDollarPurchaseOrderInquiryReq:京东一元购订单查询`
`CzmfGoodsLinkReq:超值买返商品转链`
`GoodsMaterialListReq:商品精推素材`
`JdGoodsBatchLinkReq:京东商品批量转链`
`JdOrderDetailReq:京东订单查询`
`JdUrlParseReq:京东链接解析`
`OwnerGoodsReq:我发布的商品`
`PddGoodsLinkReq:拼多多商品转链`
`TbCashGiftCreateReq:淘礼金创建`
`TbGoodsCommentReq:商品评论`
`TbGoodsCouponReq:优惠券查询`
`TbShopConvertReq:店铺转链`
`PddGoodsCategoryReq:拼多多商品类目查询`
`JdGoodsCategoryReq:京东商品类目查询`

###### `大淘客开放平台--特色栏目API--dtkApi.original`
`TbTopicListReq:官方活动(1元购)`
`DdqGoodsListReq:咚咚抢`
`RankingListReq:各大榜单`
`CatalogueReq:精选专题`
`TopicGoodsListReq:专题商品`
`OpGoodsListReq:9.9包邮精选`
`BrandListReq:品牌库`
`ListSimilerGoodsByOpenReq：猜你喜欢`
`ActivityGoodsListReq:活动商品`
`ActivityCatalogueReq:热门活动`
`LiveMaterialGoodsListReq:直播好货`
`ExplosiveGoodsListReq:每日爆品推荐`
`ExclusiveGoodsListReq:大淘客独家券商品`
`FriendsCircleListReq:朋友圈文案商品`
`GoodspriceTrendReq:商品历史券后价`
`AlbumListReq:专辑列表`
`CarouselMapResponseReq:轮播图`
`CzmfGoodsListReq:超值买返商品`
`GetBrandColumnListReq:品牌栏目`
`GetBrandGoodsListReq:单个品牌详情`
`GetHalfPriceDayReq:每日半价`
`HighCommissionSelectedReq:高佣精选`
`HistoricalNewLowCommodityReq:历史新低商品合集`
`JdBigBrandDiscountReq:京东大牌折扣`
`JdGoodspriceTrendReq:京东商品历史券后价`
`JdNewYearCommodityReq:京东年货节商品`
`JdNineFreeShippingReq:京东9.9包邮`
`JdRealTimeListReq:京东实时榜单`
`MostPopularCommodityListReq:爆品预告商品合集`
`PopularAnchorCommendReq:热门主播力荐商品`
`SubdivisionCategoryListReq:细分类目合集`
`SubdivisionCategoryRankReq:细分类目榜`
`SuperDiscountGoodsReq:折上折`
`XianBaoDetailReq:线报`

###### `大淘客开放平台--入库更新API--dtkApi.save`
`GoodsListReq:商品列表`
`GoodsByTimeReq:定时拉取`
`GoodsDetailsReq:单品详情`
`NewestGoodsReq:商品更新`
`StaleGoodsByTimeReq:失效商品`
`JdGoodsDetaillReq:京东商品详情`
`PddGoodsDetaillReq:拼多多商品详情`

###### `大淘客开放平台--搜索API--dtkApi.search`
`DtkSearchGoodsReq:大淘客搜索`
`SuggestionReq:联想词`
`SuperGoodsReq:超级搜索`
`TbServiceReq:联盟搜索`
`Top100Req:热搜记录`
`ListHotWordsReq:热搜榜`
`PddGoodsReq:拼多多联盟搜索`
`JdGoodsReq:京东联盟搜索`


#### 安装教程

1.  依赖包安装
    pip install  requests
2.  安装
    
    1)下载安装包
    
    git clone https://gitee.com/dtk-developer/openapi-sdk-python.git
    或者下载压缩包
    
    2)安装
	python setup.py install


#### 使用说明
**** 
`热搜记录`

from dtkApi.search import Top100Req

appKey = 'xxx'

appSecret = 'xxx'

version = 'v1.0.1'  # 当前版本号

gr=Top100Req(appKey,appSecret,version)

gr.setParams(type=1)

data=gr.getResponse()

print(data)

****
`商品列表`

from dtkApi.save import GoodsListReq

appKey = 'xxx'

appSecret = 'xxx'

version = 'v1.2.4'  # 当前版本号

gr=GoodsListReq(appKey,appSecret,version)

gr.setParams(pageId=1)

data=gr.getResponse()

print(data)

****
`各大榜单`

from dtkApi.original import RankingListReq

appKey = 'xxx'

appSecret = 'xxx'

version = 'v1.3.0'  # 当前版本号

gr=RankingListReq(appKey,appSecret,version)

gr.setParams(rankType=1)

data=gr.getResponse()

print(data)

****
`高效转链`

from dtkApi.basic import PrivilegeLinkReq

appKey = 'xxx'

appSecret = 'xxx'

version = 'v1.3.1'  # 当前版本号

gr=PrivilegeLinkReq(appKey,appSecret,version)

gr.setParams(goodsId="2222112")

data=gr.getResponse()

print(data)

****
`通用req方法`

appKey = 'xxx'

appSecret = 'xxx'

version = 'v1.0.1'
    
req = DefaultReq(appKey, appSecret, version)
    
req.setParams(url="tb-service/parse-content", method="GET", params={"content": "4$Y2tMdfT9OZ5$:// ZH9114"})

data = req.getResponse()

print(data)