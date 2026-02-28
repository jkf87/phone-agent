# Twilio 초기 설정 가이드

Twilio에서 전화가 작동하려면 아래 단계를 모두 완료해야 함.

## 1. 계정 생성 및 전화번호 구매

1. twilio.com 가입
2. Phone Numbers → Buy a Number → 미국 번호 구매 ($1/월)
3. 번호의 Phone Number SID 확인 (URL의 `PN`으로 시작하는 값)

## 2. Customer Profile 생성 (필수)

Voice 기능 활성화에 필요:

1. console.twilio.com → Account → Customer Profiles
2. 프로필 생성 → 정보 입력 → 제출
3. **Approved** 상태 확인 (수 분~수 시간 소요)
4. Approved 후에도 Voice 안 되면 → Twilio 지원팀에 Voice 활성화 요청

## 3. Geo Permissions

한국으로 전화하려면:

1. Voice → Settings → Geo Permissions
2. **South Korea** 체크 → 저장

## 4. 환경변수 확인

| 변수 | 위치 |
|------|------|
| TWILIO_ACCOUNT_SID | console.twilio.com 메인 화면 |
| TWILIO_AUTH_TOKEN | console.twilio.com 메인 화면 |
| TWILIO_PHONE_NUMBER_SID | Phone Numbers → 번호 클릭 → URL의 PN값 |

## 5. 수신자 주의사항

- 일부 한국 통신사는 국제전화 수신을 기본 차단
- 수신자가 통신사 앱/고객센터에서 국제전화 수신 허용 필요
