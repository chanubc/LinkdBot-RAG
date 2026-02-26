다음 순서대로 실행하세요. 각 단계는 반드시 순서를 지킬 것.

## 1. 기능 설명 확인
사용자가 기능 설명을 제공하지 않았다면 먼저 물어보세요.
이미 제공했다면 그대로 사용하세요.

## 2. GitHub 이슈 생성
`.github/ISSUE_TEMPLATE/issue_template.md` 형식에 맞춰 이슈를 생성하세요.

```bash
gh issue create --title "[FEAT] {기능 설명}" --body "$(cat <<'EOF'
## 📌 𝗧𝗮𝘀𝗸
- [ ] {기능 설명}

## 💡 𝗥𝗲𝗳𝗲𝗿𝗲𝗻𝗰𝗲

EOF
)"
```

출력에서 이슈 번호 N을 추출하세요.

## 3. main 최신화
작업 시작 전에 반드시 main 브랜치를 최신 상태로 만드세요.

```bash
git checkout main
git pull origin main
```

## 4. 브랜치 생성 및 체크아웃
브랜치 이름 규칙: `feat/#N-{영어 kebab-case 설명}`

```bash
git checkout -b feat/#N-{설명}
```

예시: `feat/#34-add-ask-command`

## 5. 완료 메시지 출력
```
✅ 준비 완료!
📌 이슈: #{N}
🌿 브랜치: feat/#N-{설명}

이제 작업을 시작하세요.
```

## 6. 작업 완료 후 PR 생성 (작업 완료 시 별도 실행)
`.github/PULL_REQUEST_TEMPLATE.md` 형식에 맞춰 PR을 생성하세요.

```bash
gh pr create --title "[FEAT/#N] {기능 설명}" --body "$(cat <<'EOF'
## 📌 𝗜𝘀𝘀𝘂𝗲𝘀
closed #{N}

## 📝 𝗦𝘂𝗺𝗺𝗮𝗿𝘆
> 변경 사항을 간략히 설명해주세요.

-

## ✅ 𝗖𝗵𝗲𝗰𝗸𝗹𝗶𝘀𝘁
- [ ] 레이어 간 의존성 방향 준수 (Presentation → Application → Domain ← Infrastructure)
- [ ] 모든 함수/메서드에 Type Hint 작성
- [ ] 외부 I/O는 Interface(ABC) 타입으로 의존
- [ ] DI는 FastAPI Depends만 사용, 내부 직접 인스턴스화 금지
- [ ] 모든 I/O는 async/await 사용

## 📸 𝗦𝗰𝗿𝗲𝗲𝗻𝘀𝗵𝗼𝘁

| 구현 내용 | 스크린샷 |
| :-------: | :------: |
|           |          |

## 💡 𝗥𝗲𝗳𝗲𝗿𝗲𝗻𝗰𝗲

EOF
)"
```

## 7. PR 머지
GitHub UI에서 "Create a merge commit" 선택 후 병합. 또는 CLI:

```bash
gh pr merge {PR_NUMBER} --merge
```
