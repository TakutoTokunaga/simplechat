# lambda/index.py
import json
import os
import boto3
import re  # 正規表現モジュールをインポート
from botocore.exceptions import ClientError

# --- 追加: urllib をインポート ---
import urllib.request
import urllib.error
import ssl               # Colab + cloudflared の自己署名証明書対策
# 既存 import 行の上書きにならないようにだけ注意

# --- 追記: 推論 API URL を環境変数で受け取る ---
PREDICT_URL = os.environ.get("https://3695-34-142-177-53.ngrok-free.app")   # 例: "https://xxxxx.trycloudflare.com/predict"

def call_private_model(message: str) -> str:
    """
    外部 FastAPI 推論エンドポイントを叩いて応答文字列を返す。
    urllib.request しか使えない前提。
    """
    if not PREDICT_URL:
        raise RuntimeError("環境変数 PREDICT_URL が未設定です。")
    
    # POST body
    data = json.dumps({"message": message}).encode("utf-8")
    req = urllib.request.Request(
        PREDICT_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    # Colab + cloudflared は自己署名 cert のことがあるので verify を手抜きで無効化
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            answer = json.loads(body).get("answer", "").strip()
            return answer or "[Empty answer]"
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API HTTPError {e.code}: {e.read().decode()}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"API URLError: {e.reason}") from e

# --- lambda_handler を修正 ---
def lambda_handler(event, context):
    try:
        # 受信メッセージ抽出（元コードと同じ）
        body = json.loads(event["body"])
        message = body["message"]

        # 独自モデルに投げる
        assistant_response = call_private_model(message)

        # 返却
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "OPTIONS,POST"
            },
            "body": json.dumps({
                "success": True,
                "response": assistant_response,
                "conversationHistory": []  # 必要なら元の履歴を返す
            })
        }

    except Exception as error:
        return {
            "statusCode": 500,
            "headers": { "Content-Type": "application/json" },
            "body": json.dumps({ "success": False, "error": str(error) })
        }


# # Lambda コンテキストからリージョンを抽出する関数
# def extract_region_from_arn(arn):
#     # ARN 形式: arn:aws:lambda:region:account-id:function:function-name
#     match = re.search('arn:aws:lambda:([^:]+):', arn)
#     if match:
#         return match.group(1)
#     return "us-east-1"  # デフォルト値

# # グローバル変数としてクライアントを初期化（初期値）
# bedrock_client = None

# # モデルID
# MODEL_ID = os.environ.get("MODEL_ID", "us.amazon.nova-lite-v1:0")

# def lambda_handler(event, context):
#     try:
#         # コンテキストから実行リージョンを取得し、クライアントを初期化
#         global bedrock_client
#         if bedrock_client is None:
#             region = extract_region_from_arn(context.invoked_function_arn)
#             bedrock_client = boto3.client('bedrock-runtime', region_name=region)
#             print(f"Initialized Bedrock client in region: {region}")
        
#         print("Received event:", json.dumps(event))
        
#         # Cognitoで認証されたユーザー情報を取得
#         user_info = None
#         if 'requestContext' in event and 'authorizer' in event['requestContext']:
#             user_info = event['requestContext']['authorizer']['claims']
#             print(f"Authenticated user: {user_info.get('email') or user_info.get('cognito:username')}")
        
#         # リクエストボディの解析
#         body = json.loads(event['body'])
#         message = body['message']
#         conversation_history = body.get('conversationHistory', [])
        
#         print("Processing message:", message)
#         print("Using model:", MODEL_ID)
        
#         # 会話履歴を使用
#         messages = conversation_history.copy()
        
#         # ユーザーメッセージを追加
#         messages.append({
#             "role": "user",
#             "content": message
#         })
        
#         # Nova Liteモデル用のリクエストペイロードを構築
#         # 会話履歴を含める
#         bedrock_messages = []
#         for msg in messages:
#             if msg["role"] == "user":
#                 bedrock_messages.append({
#                     "role": "user",
#                     "content": [{"text": msg["content"]}]
#                 })
#             elif msg["role"] == "assistant":
#                 bedrock_messages.append({
#                     "role": "assistant", 
#                     "content": [{"text": msg["content"]}]
#                 })
        
#         # invoke_model用のリクエストペイロード
#         request_payload = {
#             "messages": bedrock_messages,
#             "inferenceConfig": {
#                 "maxTokens": 512,
#                 "stopSequences": [],
#                 "temperature": 0.7,
#                 "topP": 0.9
#             }
#         }
        
#         print("Calling Bedrock invoke_model API with payload:", json.dumps(request_payload))
        
#         # invoke_model APIを呼び出し
#         response = bedrock_client.invoke_model(
#             modelId=MODEL_ID,
#             body=json.dumps(request_payload),
#             contentType="application/json"
#         )
        
#         # レスポンスを解析
#         response_body = json.loads(response['body'].read())
#         print("Bedrock response:", json.dumps(response_body, default=str))
        
#         # 応答の検証
#         if not response_body.get('output') or not response_body['output'].get('message') or not response_body['output']['message'].get('content'):
#             raise Exception("No response content from the model")
        
#         # アシスタントの応答を取得
#         assistant_response = response_body['output']['message']['content'][0]['text']
        
#         # アシスタントの応答を会話履歴に追加
#         messages.append({
#             "role": "assistant",
#             "content": assistant_response
#         })
        
#         # 成功レスポンスの返却
#         return {
#             "statusCode": 200,
#             "headers": {
#                 "Content-Type": "application/json",
#                 "Access-Control-Allow-Origin": "*",
#                 "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
#                 "Access-Control-Allow-Methods": "OPTIONS,POST"
#             },
#             "body": json.dumps({
#                 "success": True,
#                 "response": assistant_response,
#                 "conversationHistory": messages
#             })
#         }
        
#     except Exception as error:
#         print("Error:", str(error))
        
#         return {
#             "statusCode": 500,
#             "headers": {
#                 "Content-Type": "application/json",
#                 "Access-Control-Allow-Origin": "*",
#                 "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
#                 "Access-Control-Allow-Methods": "OPTIONS,POST"
#             },
#             "body": json.dumps({
#                 "success": False,
#                 "error": str(error)
#             })
#         }