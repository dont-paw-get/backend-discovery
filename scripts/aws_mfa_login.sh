#!/bin/bash
# KOSA 교육 계정 MFA 임시 세션 토큰 발급 및 환경변수 설정 스크립트
# 사용법: source scripts/aws_mfa_login.sh <MFA_OTP_6자리>

if [ -z "$1" ]; then
  echo "❌ OTP 6자리를 입력해주세요."
  echo "사용법: source scripts/aws_mfa_login.sh <OTP_6자리>"
  return 1 2>/dev/null || exit 1
fi

# 기존 터미널에 남아있는 만료된 세션 환경변수를 먼저 비웁니다
unset AWS_SESSION_TOKEN AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY

MFA_SERIAL="arn:aws:iam::594532711953:mfa/kosa15"
TOKEN_CODE="$1"

CREDENTIALS=$(env -u AWS_SESSION_TOKEN -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY aws sts get-session-token --serial-number "$MFA_SERIAL" --token-code "$TOKEN_CODE" --duration-seconds 43200 --output json 2>&1)

if [ $? -ne 0 ]; then
  echo "❌ MFA 인증에 실패했습니다:"
  echo "$CREDENTIALS"
  return 1 2>/dev/null || exit 1
fi

# Python을 이용해 JSON 파싱 후 export
eval $(python3 -c "
import json, sys
data = json.loads('''$CREDENTIALS''')['Credentials']
print(f'export AWS_ACCESS_KEY_ID=\"{data[\"AccessKeyId\"]}\"')
print(f'export AWS_SECRET_ACCESS_KEY=\"{data[\"SecretAccessKey\"]}\"')
print(f'export AWS_SESSION_TOKEN=\"{data[\"SessionToken\"]}\"')
")

echo "✅ AWS MFA 인증 성공! (User: kosa15)"
echo "이제 'uv run uvicorn discovery.main:app --reload --port 8000' 을 실행하세요."
