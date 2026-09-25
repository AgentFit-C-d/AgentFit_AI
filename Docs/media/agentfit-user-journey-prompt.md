# AgentFit 사용자 흐름 웹툰 제작 기록

> 이 기록과 기존 생성 이미지는 Claude Code를 초기 지원 대상으로 삼던 당시 자료다. 현재 초기 지원 대상은 Codex다. 이미지를 재사용하거나 다시 생성하기 전에 Client 명칭·화면·설정 예시를 Codex 기준으로 고쳐야 한다.

제작 방식: 내장 image_gen 이미지 생성 도구.
용도: 팀 공유용 8컷 기획 예시. 실제 구현·설치·검증 완료를 의미하지 않는다.

## 최종 생성 프롬프트

Use case: illustration-story.
Asset type: a finished Korean explainer webtoon for sharing with university project teammates over KakaoTalk.
Primary request: Show the planned AgentFit user journey, from an overwhelming AI setup problem to a user manually applying downloaded settings in their own project and checking their tools. This is a product concept, not a claim of an already running service.

Create ONE polished portrait comic sheet with exactly 8 large panels, 2 columns by 4 rows, reading left to right then down. Prefer 1536 x 2560 or a similarly spacious high-resolution portrait canvas. A small title area above the grid and a short note below it. This must feel like a real friendly Korean slice-of-life webtoon, with expressive character acting, varied close-ups, clean ink lines, flat gentle colors and soft shading, ample white speech bubbles, attractive balanced gutters, readable Korean lettering. Use a consistent young adult Korean student developer at their laptop in every character scene. Keep outfit and face consistent. The character is building an exercise-tracking web app and is responsible for backend development. Do not introduce a robot or magical autonomous assistant.

Title text, exactly: "AgentFit, 이렇게 사용해요"
Subtitle text, exactly: "기획서에서 내 개발환경 적용까지"

Panel 1, upper left:
Number and title: "01  어디서 시작하지?"
Scene: the developer is mildly overwhelmed at a laptop, with small floating text cards "MCP", "Skill", "설정". Focus on expression and a simple realistic desk, not clutter.
Speech bubble, exactly: "백엔드 개발은 맡았는데… AI 설정은 뭘 쓰지?"

Panel 2, upper right:
Number and title: "02  기획서 입력"
Scene: close-up of the user's hand uploading a PDF to a browser page clearly labeled "AgentFit"; the small step indicator says "GitHub 로그인 완료".
Large readable UI labels: "운동 기록 서비스.pdf" and a button "분석하기".
Speech bubble, exactly: "기획서를 올려볼까?"

Panel 3, second row left:
Number and title: "03  내용과 환경 확인"
Scene: the user actively reviews an extracted project profile and fills in their role and environment.
Only these few legible UI rows: "배포: 미정", "역할: 백엔드", "환경: Windows · Claude Code".
Button exactly: "수정 후 저장".
Speech bubble, exactly: "맞는지 확인하고, 내 환경도 알려줘!"

Panel 4, second row right:
Number and title: "04  필요한 구성 선택"
Scene: browser shows two selected recommendation cards and an unselected optional card.
Card labels exactly: "프로젝트 개발 규칙", "API 검토 Skill", "DB 조회 도구 · 선택".
A tiny explanation under the first two cards, if space permits: "내 업무에 필요한 이유도 함께".
Speech bubble, exactly: "필요한 것만 골라야지."
These are illustrative capability categories, not fake verified real commercial tools. Do not claim any tool has actually passed tests.

Panel 5, third row left:
Number and title: "05  권한과 내용 승인"
Scene: browser preview with readable permission chips "조회: 사용 시 확인", "변경: 허용 안 함"; nearby small file-content preview boxes and clear label "기존 파일 미확인".
A prominent button exactly: "내용 확인 후 승인".
Speech bubble, exactly: "권한과 파일 내용을 먼저 확인!"
Do not show automatic operating system writes. Client permissions and user consent should be visually distinct from generation.

Panel 6, third row right:
Number and title: "06  설정 다운로드"
Scene: user clicks a download button, receiving a clearly illustrated ZIP file together with an illustrated application guide.
Readable ZIP label: "agentfit-config.zip".
Guide label: "적용 안내서".
Speech bubble, exactly: "설정 파일과 적용 방법을 받았어!"

Panel 7, bottom left:
Number and title: "07  내 프로젝트에 적용"
Scene: the user's hand on the mouse actively moves selected files from an unpacked download folder into THEIR local project folder. Clearly a manual user action.
Large target folder label: "내 프로젝트".
Visible file/folder labels: "CLAUDE.md", ".claude/", ".mcp.json".
Speech bubble, exactly: "안내된 위치에 넣고, 기존 파일은 비교!"
Small note within panel exactly: "기존 파일은 백업 후 반영".
No blind overwrite, no one-click auto-install promise.

Panel 8, bottom right:
Number and title: "08  인증하고 직접 확인"
Scene: user is inside a terminal-like Claude Code window in their project, completes a needed authentication step and tries a harmless API review Skill. Show a satisfied, focused expression, not a magical 'all environments verified' badge.
Window label: "Claude Code".
Small step label: "필요한 설치·인증".
Visible typed command: "/api-review".
Speech bubble, exactly: "이제 내 프로젝트에서 써보자!"
A small caption exactly: "선택한 도구의 동작을 직접 확인".

Footer text, exactly: "기획 예시 · 다운로드 후 파일 적용과 필요한 인증은 사용자가 진행합니다."

Constraints: Render the Korean copy accurately and legibly, verbatim; don't add extra speech bubbles or filler text. Keep each panel focused on ONE major action, allow short captions and UI labels at large size. Clean sans-serif Korean typography for UI/captions, friendly readable Korean comic lettering for speech. No watermark. No stock corporate infographic aesthetic. No photorealism. No claims of one-click installation, automatic PC access, guaranteed safety, or system-verified success. No secret keys, passwords, or fabricated real MCP endpoints. No additional caption paragraphs. Keep titles, faces, and bubbles fully inside the canvas.
