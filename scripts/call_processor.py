"""
Call Log Processor: 통화 종료 후 로그 분석 및 요청 처리
"""
import os
import json
from datetime import datetime
from openai import OpenAI

CALL_LOGS_DIR = os.path.join(os.path.dirname(__file__), "call_logs")

def ensure_logs_dir():
    """로그 디렉토리 생성"""
    if not os.path.exists(CALL_LOGS_DIR):
        os.makedirs(CALL_LOGS_DIR)

def save_call_log(conversation: list) -> str:
    """통화 로그를 파일로 저장"""
    ensure_logs_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{timestamp}.json"
    filepath = os.path.join(CALL_LOGS_DIR, filename)
    
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "conversation": conversation
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)
    
    return filepath

def extract_requests_from_log(conversation: list) -> list:
    """OpenAI API를 사용해서 대화에서 요청 추출"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return []
    
    client = OpenAI(api_key=api_key)
    
    # 대화 텍스트 구성
    conversation_text = "\n".join([
        f"[{item['role']}] {item['content']}" 
        for item in conversation
    ])
    
    prompt = f"""다음 전화 통화 내용에서 사용자가 요청한 것들을 추출해줘.

통화 내용:
{conversation_text}

요청 타입:
- reminder: 알림/리마인더 (예: "내일 7시에 모닝콜 해줘", "저녁 6시에 약속 있어")
- todo: 할 일 (예: "마트에서 우유 사와", "문서 작성해야 해")
- calendar: 일정 (예: "다음 주 월요일에 회의 있어")
- call_back: 콜백 요청 (예: "나중에 다시 전화해줘")

JSON 배열로 반환해줘:
[
  {{"type": "reminder", "content": "내용", "datetime": "YYYY-MM-DD HH:MM (있으면)"}},
  ...
]

요청이 없으면 빈 배열 []을 반환해줘.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # JSON 추출
        if "[" in result_text and "]" in result_text:
            start = result_text.index("[")
            end = result_text.rindex("]") + 1
            json_str = result_text[start:end]
            return json.loads(json_str)
        
        return []
    except Exception as e:
        print(f"Error extracting requests: {e}")
        return []

def save_processed_requests(requests: list, log_file: str) -> str:
    """처리된 요청을 저장"""
    ensure_logs_dir()
    
    processed_data = {
        "log_file": os.path.basename(log_file),
        "processed_at": datetime.now().isoformat(),
        "requests": requests,
        "status": "pending"  # pending, completed, failed
    }
    
    filepath = os.path.join(CALL_LOGS_DIR, "requests_processed.json")
    
    # 기존 데이터 로드
    existing = []
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            existing = json.load(f)
    
    existing.append(processed_data)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    
    return filepath

def process_call_end(conversation: list) -> dict:
    """통화 종료 시 호출되는 메인 함수"""
    # 1. 로그 저장
    log_file = save_call_log(conversation)
    print(f"📝 통화 로그 저장: {log_file}")
    
    # 2. 요청 추출
    requests = extract_requests_from_log(conversation)
    print(f"🔍 추출된 요청: {len(requests)}개")
    
    # 3. 요청 저장
    if requests:
        processed_file = save_processed_requests(requests, log_file)
        print(f"✅ 요청 처리 완료: {processed_file}")
    
    return {
        "log_file": log_file,
        "requests": requests
    }

if __name__ == "__main__":
    # 테스트
    test_conversation = [
        {"role": "user", "content": "내일 아침 7시에 모닝콜 해줘"},
        {"role": "assistant", "content": "알겠어! 내일 7시에 모닝콜 할게."},
        {"role": "user", "content": "그리고 저녁 6시에 약속 있으니까 리마인더도 해줘"},
    ]
    
    result = process_call_end(test_conversation)
    print(json.dumps(result, ensure_ascii=False, indent=2))
