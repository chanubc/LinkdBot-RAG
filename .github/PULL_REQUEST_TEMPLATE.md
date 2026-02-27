<!-- title: [PREFIX/#이슈번호] 작업 제목 -->

## 📌 𝗜𝘀𝘀𝘂𝗲𝘀
closed #이슈번호

## 📝 𝗦𝘂𝗺𝗺𝗮𝗿𝘆
> 변경 사항을 간략히 설명해주세요.

-

## 🧪 𝗧𝗲𝘀𝘁
> 이 PR을 로컬에서 테스트하려면 다음을 실행하세요:
```bash
# 마이그레이션 적용 (변경 사항이 있을 경우)
alembic upgrade head

# 개발 서버 실행
uvicorn app.main:app --reload --port 8000

# 테스트 실행
pytest
```

> **필수 테스트:**
- [ ] 웹훅 엔드포인트: `POST /api/v1/webhook/telegram` (tests/test_webhook.http 참고)
- [ ] `/start`, `/memo`, `/search`, `/ask` 명령어 정상 작동
- [ ] URL 저장 정상 작동

## 📸 𝗦𝗰𝗿𝗲𝗲𝗻𝘀𝗵𝗼𝘁

<!-- 작업한 화면이 있다면 스크린 샷으로 첨부해주세요. -->
<!-- 큰 이미지, png 짜를때 재사용하세요.
<img src = "이미지주소" width = "50%" height = "50%">
 -->

|    구현 내용    |   스크린샷   |
| :-------------: | :----------: |
| ex. 로그인 화면 | 파일첨부바람 |

## 💡 𝗥𝗲𝗳𝗲𝗿𝗲𝗻𝗰𝗲
