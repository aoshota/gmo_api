import requests
from datetime import datetime,timedelta,timezone
from dateutil.relativedelta import relativedelta
import pandas as pd
import hmac
import hashlib
import time
import json

class gmo():

	def __init__(self,apikey='',secretkey=''):
		self.endpoint = 'https://api.coin.z.com/public' # パブリックAPIのエンドポイント
		self.endpoint_private = 'https://api.coin.z.com/private' # プライベートAPIのエンドポイント
		self.jst = timezone(timedelta(hours=+9), 'JST') # タイムゾーンを指定(JST)
		self.apikey = apikey # APIKEY
		self.secretkey = secretkey #SECRETKEY

	# get_klinesで使うAPIで取得したklineを必要なものだけ辞書型に変換する関数
	def _kline_to_dict(self,opentime,dict,kline):
		for x in kline:
			opentime.append(datetime.fromtimestamp(int(x['openTime'])/1000,self.jst))
			dict['open'].append((x['open']))
			dict['high'].append(x['high'])
			dict['low'].append(x['low'])
			dict['close'].append(x['close'])
			dict['volume'].append(x['volume'])
		return opentime,dict

	# 取り扱い通貨
	def market(self):
		market = [
			'BTC',
			'ETH',
			'BCH',
			'LTC',
			'XRP',
			'XEM',
			'XLM',
			'BAT',
			'OMG',
			'XTZ',
			'QTUM',
			'ENJ',
			'DOT',
			'ATOM',
			'MKR',
			'DAI',
			'XYM',
			'MONA',
			'FCR',
			'ADA',
			'LINK',
			'BTC_JPY',
			'ETH_JPY',
			'BCH_JPY',
			'LTC_JPY',
			'XRP_JPY'
		]

		return market

	# 取引所のステータスを取得
	def exchange_status(self):
		path = '/v1/status'
		return requests.get(self.endpoint + path)

	# 最新レートを取得
	def get_ticker(self,symbol):
		path = '/v1/ticker?symbol=' + symbol
		return requests.get(self.endpoint + path)

	# 板情報を取得
	def get_orderbooks(self,symbol):
		path = '/v1/orderbooks?symbol=' + symbol
		return requests.get(self.endpoint + path)

	# 約定履歴を取得
	def get_trades(self,symbol):
		path = '/v1/trades?symbol=' + symbol + '&page=1&count=10'
		return requests.get(self.endpoint + path)

	# klineデータを取得
	# limitがあるときはlimitの数だけklineを返す
	# limitがないときはstartから今日までのklineを返す
	def get_klines(self,symbol,interval,start,limit=False):
		# 日付指定が変わるinterval(4時間足以上)
		long_range = ['4hour','8hour','12hour','1day','1week','1month']
		if interval in long_range: date_format = """%Y""" # 4時間足以上のinterval
		else: date_format = """%Y%m%d""" # 1時間足以下のinterval
		start_day_before = start - timedelta(days=1) # 当日を指定しても午前6時からのデータになるため前日の日付を使う
		today = datetime.now(self.jst) # 今日の日付(JST)
		# GMOコインのデータは午前6時から日付が変わるため6時を区切りに日付を指定
		if today.hour >= 6: today = today
		else: today -= timedelta(days=1)

		# ローソク足データをデータフレームに変換する際に使う変数
		opentime = []
		data = {
			'open': [],
			'high': [],
			'low': [],
			'close': [],
			'volume': [],
		}
		# 取得件数を指定された場合、最新のデータを指定された件数返す
		if limit:
			# 今日のデータから指定件数を満たすまでループ
			since = today
			while True:
				path = '/v1/klines?symbol=' + symbol + '&interval=' + interval + '&date=' + since.strftime(date_format)
				response = requests.get(self.endpoint + path).json()
				kline = response['data']
				kline.reverse() # 最新のデータが配列の最初にくるようにklineを逆に並び替える
				opentime,data = self._kline_to_dict(opentime,data,kline) # 取得したklineを配列に格納
				since -= timedelta(days=1)
				if len(opentime) >= limit: break # 指定件数に達したらループを抜ける
			df = pd.DataFrame(data,index=opentime).iloc[::-1,:] # 最新のデータが一番最後になるようにデータフレームを逆に並び替える
			res = df.iloc[-limit:] # 指定件数のデータ数だけ返す
		# 取得件数を指定されていない場合、データ取得日から今日までのデータを返す
		else:
			if interval in long_range: period = today.year - start_day_before.year # 4時間足以上は年数で指定するため、取得開始日から今日までの年数の差分を取る
			else: period = (today - start_day_before).days # 1時間足以下は日数まで指定するため、取得開始日から今日までの日数の差分を取る
			since = start_day_before
			for i in range(period+1):
				path = '/v1/klines?symbol=' + symbol + '&interval=' + interval + '&date=' + since.strftime(date_format)
				response = requests.get(self.endpoint + path).json()
				kline = response['data']
				opentime,data = self._kline_to_dict(opentime,data,kline) # 取得したklineを配列に格納
				if interval in long_range: since += relativedelta(years=1) # 4時間足以上は年数を+1してklineを取得
				else: since += timedelta(days=1) # 1時間足以下は日数を+1してklineを取得
			df = pd.DataFrame(data,index=opentime)
			res = df[start:] # 指定日からのデータを返す
		return res

	# 余力情報を取得
	def get_margin(self):
		timestamp = '{0}000'.format(int(time.mktime(datetime.now().timetuple())))
		method = 'GET'
		path = '/v1/account/margin'
		text = timestamp + method + path
		sign = hmac.new(bytes(self.secretkey.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()
		headers = {
			"API-KEY": self.apikey,
			"API-TIMESTAMP": timestamp,
			"API-SIGN": sign
		}

		return requests.get(self.endpoint_private + path, headers=headers)

	# 資産残高を取得
	def get_assets(self):
		timestamp = '{0}000'.format(int(time.mktime(datetime.now().timetuple())))
		method = 'GET'
		path = '/v1/account/assets'
		text = timestamp + method + path
		sign = hmac.new(bytes(self.secretkey.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()
		headers = {
			"API-KEY": self.apikey,
			"API-TIMESTAMP": timestamp,
			"API-SIGN": sign
		}

		return requests.get(self.endpoint_private + path, headers=headers)

	# 新規注文
	def create_new_order(self,symbol,side,type,price,size,timeInForce=''):
		timestamp = '{0}000'.format(int(time.mktime(datetime.now().timetuple())))
		method = 'POST'
		path = '/v1/order'
		reqBody = {
			"symbol": symbol,
			"side": side,
			"executionType": type,
			"timeInForce": timeInForce,
			"price": price,
			"size": size
		}
		if timeInForce == '':reqBody.pop('timeInForce')
		if type == 'MARKET':reqBody.pop('price')
		text = timestamp + method + path + json.dumps(reqBody)
		sign = hmac.new(bytes(self.secretkey.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()
		headers = {
			"API-KEY": self.apikey,
			"API-TIMESTAMP": timestamp,
			"API-SIGN": sign
		}

		return requests.post(self.endpoint_private + path, headers=headers, data=json.dumps(reqBody))

	# 注文情報取得
	def get_order_info(self,orderIds):
		timestamp = '{0}000'.format(int(time.mktime(datetime.now().timetuple())))
		method = 'GET'
		path = '/v1/orders'
		text = timestamp + method + path
		sign = hmac.new(bytes(self.secretkey.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()
		parameters = { "orderId": orderIds }
		headers = {
			"API-KEY": self.apikey,
			"API-TIMESTAMP": timestamp,
			"API-SIGN": sign
		}

		return requests.get(self.endpoint_private + path, headers=headers, params=parameters)

	# 注文キャンセル
	def cancel_order(self,orderId):
		timestamp = '{0}000'.format(int(time.mktime(datetime.now().timetuple())))
		method = 'POST'
		path = '/v1/cancelOrder'
		reqBody = {
			"orderId": orderId
		}
		text = timestamp + method + path + json.dumps(reqBody)
		sign = hmac.new(bytes(self.secretkey.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()

		headers = {
			"API-KEY": self.apikey,
			"API-TIMESTAMP": timestamp,
			"API-SIGN": sign
		}

		return requests.post(self.endpoint_private + path, headers=headers, data=json.dumps(reqBody))

	# 約定情報取得
	def get_executions(self,orderId):
		timestamp = '{0}000'.format(int(time.mktime(datetime.now().timetuple())))
		method = 'GET'
		path = '/v1/executions'
		text = timestamp + method + path
		sign = hmac.new(bytes(self.secretkey.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()
		parameters = {
			"orderId": orderId
		}
		headers = {
			"API-KEY": self.apikey,
			"API-TIMESTAMP": timestamp,
			"API-SIGN": sign
		}

		return requests.get(self.endpoint_private + path, headers=headers, params=parameters)

	# 決済注文
	def create_close_order(self,symbol,side,type,price,size,positionId,timeInForce=''):
		timestamp = '{0}000'.format(int(time.mktime(datetime.now().timetuple())))
		method = 'POST'
		path = '/v1/closeOrder'
		reqBody = {
			"symbol": symbol,
			"side": side,
			"executionType": type,
			"timeInForce": timeInForce,
			"price": price,
			"settlePosition": [
				{
					"positionId": positionId,
					"size": size
				}
			]
		}

		text = timestamp + method + path + json.dumps(reqBody)
		sign = hmac.new(bytes(self.secretkey.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()

		headers = {
			"API-KEY": self.apikey,
			"API-TIMESTAMP": timestamp,
			"API-SIGN": sign
		}

		return requests.post(self.endpoint_private + path, headers=headers, data=json.dumps(reqBody))

	# 注文変更
	def change_order(self,orderId,price):
		timestamp = '{0}000'.format(int(time.mktime(datetime.now().timetuple())))
		method = 'POST'
		path = '/v1/changeOrder'
		reqBody = {
			"orderId": orderId,
			"price": price,
		}
		text = timestamp + method + path + json.dumps(reqBody)
		sign = hmac.new(bytes(self.secretkey.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()
		headers = {
			"API-KEY": self.apikey,
			"API-TIMESTAMP": timestamp,
			"API-SIGN": sign
		}

		return requests.post(self.endpoint_private + path, headers=headers, data=json.dumps(reqBody))

	# 注文一括キャンセル
	def cancel_all_order(self,symbol_arr):
		timestamp = '{0}000'.format(int(time.mktime(datetime.now().timetuple())))
		method    = 'POST'
		path      = '/v1/cancelBulkOrder'
		reqBody = {
			"symbols": symbol_arr,
		}

		text = timestamp + method + path + json.dumps(reqBody)
		sign = hmac.new(bytes(self.secretkey.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()

		headers = {
			"API-KEY": self.apikey,
			"API-TIMESTAMP": timestamp,
			"API-SIGN": sign
		}

		requests.post(self.endpoint_private + path, headers=headers, data=json.dumps(reqBody))

	# 建玉サマリー取得
	def get_position_summary(self,symbol):
		timestamp = '{0}000'.format(int(time.mktime(datetime.now().timetuple())))
		method    = 'GET'
		path      = '/v1/positionSummary'

		text = timestamp + method + path
		sign = hmac.new(bytes(self.secretkey.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()
		parameters = {
			"symbol": symbol
		}

		headers = {
			"API-KEY": self.apikey,
			"API-TIMESTAMP": timestamp,
			"API-SIGN": sign
		}

		return requests.get(self.endpoint_private + path, headers=headers, params=parameters)

	# 一括決済注文
	def close_all_order(self,symbol,side,type,size):
		timestamp = '{0}000'.format(int(time.mktime(datetime.now().timetuple())))
		method    = 'POST'
		path      = '/v1/closeBulkOrder'
		reqBody = {
			"symbol": symbol,
			"side": side,
			"executionType": type,
			"size": size
		}

		text = timestamp + method + path + json.dumps(reqBody)
		sign = hmac.new(bytes(self.secretkey.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()

		headers = {
			"API-KEY": self.apikey,
			"API-TIMESTAMP": timestamp,
			"API-SIGN": sign
		}

		return requests.post(self.endpoint_private + path, headers=headers, data=json.dumps(reqBody))

	# 建玉一覧を取得
	def get_open_position(self,symbol):
		timestamp = '{0}000'.format(int(time.mktime(datetime.now().timetuple())))
		method    = 'GET'
		path      = '/v1/openPositions'

		text = timestamp + method + path
		sign = hmac.new(bytes(self.secretkey.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()
		parameters = {
			"symbol": symbol,
			"page": 1,
			"count": 100
		}

		headers = {
			"API-KEY": self.apikey,
			"API-TIMESTAMP": timestamp,
			"API-SIGN": sign
		}

		return requests.get(self.endpoint_private + path, headers=headers, params=parameters)

	# 最新の約定一覧を取得
	def get_latest_executions(self,symbol):
		timestamp = '{0}000'.format(int(time.mktime(datetime.now().timetuple())))
		method    = 'GET'
		path      = '/v1/latestExecutions'

		text = timestamp + method + path
		sign = hmac.new(bytes(self.secretkey.encode('ascii')), bytes(text.encode('ascii')), hashlib.sha256).hexdigest()
		parameters = {
			"symbol": symbol,
			"page": 1,
			"count": 100
		}

		headers = {
			"API-KEY": self.apikey,
			"API-TIMESTAMP": timestamp,
			"API-SIGN": sign
}

		return requests.get(self.endpoint_private + path, headers=headers, params=parameters)
