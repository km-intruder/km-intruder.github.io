# 게시글 추가 방법

`전문대 현황`(colleges)과 `산업 현황`(industry) 탭은 이 폴더의 글을 목록으로 보여 줍니다.

1. `posts/<분류>/YYYY-MM.md` 파일을 만듭니다. 본문은 마크다운이며, 표·링크를 쓸 수 있습니다.
   - 중요한 부분: `<span class="alert">**강조할 내용**</span>` (빨간색)
   - 출처 묶음: `<div class="sources">` … `</div>` (앞뒤에 빈 줄)
2. 같은 폴더 `index.json`에 항목을 하나 추가합니다. 목록은 `date` 최신순으로 자동 정렬됩니다.

```json
{
 "slug": "2026-11",
 "date": "2026-11-02",
 "title": "2026년 11월 · 제목",
 "summary": "목록에 보일 한두 줄 요약",
 "tags": ["태그"],
 "file": "2026-11.md"
}
```

글 주소: `colleges.html?post=2026-11`, `industry.html?post=2026-11`
