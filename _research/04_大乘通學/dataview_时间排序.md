
```dataviewjs
const currentFolder = dv.current().file.folder;
const pages = dv.pages('"' + currentFolder + '"')
  .where(function(p) {
    const name = p.file.name;
    return name && name.indexOf('仪表盘') === -1 && name.indexOf('編目錄') === -1 && name !== dv.current().file.name;
  });

const withDate = [];
const withoutDate = [];

for (let i = 0; i < pages.length; i++) {
  const page = pages[i];
  const cy = page.create_y || '';
  const cm = page.create_m || '';
  const cd = page.create_d || '';
  const py = page.publish_y || '';
  const pm = page.publish_m || '';
  const pd = page.publish_d || '';
  const location = page.location || '';
  const publication = page.publication || '';

  const hasCreate = !!(cy || cm || cd);
  const hasPublish = !!(py || pm || pd);

  let time = '';
  let loc = '';
  let pub = '';

  const hasSeason = location && /^[春夏秋冬]/.test(location);

  if (hasCreate) {
    if (cy && !cm && !cd && !hasSeason && py && pm && cy === py) {
      time = py + (pm ? '.' + pm : '') + (pd ? '.' + pd : '');
      loc = location ? '(' + location + ')' : '';
      pub = publication;
    } else {
      time = cy + (cm ? '.' + cm : '') + (cd ? '.' + cd : '');
      loc = location;
      pub = publication;
      if (!location && publication) {
        pub = '(' + publication + ')';
      }
    }
  } else if (hasPublish) {
    time = py + (pm ? '.' + pm : '') + (pd ? '.' + pd : '');
    pub = publication;
  }

  if (time) {
    withDate.push({ time: time, loc: loc, pub: pub, link: page.file.link });
  } else {
    withoutDate.push({ loc: location, pub: publication, link: page.file.link });
  }
}

withDate.sort(function(a, b) {
  if (a.time < b.time) return -1;
  if (a.time > b.time) return 1;
  return 0;
});

const rows = [];
for (let j = 0; j < withDate.length; j++) {
  const d = withDate[j];
  rows.push([d.time, d.loc, d.pub, d.link]);
}
for (let k = 0; k < withoutDate.length; k++) {
  const u = withoutDate[k];
  rows.push(['无日期', u.loc, u.pub, u.link]);
}

dv.table(['时间', '开示地', '刊物', '文章名'], rows);
```

## 使用方式
通用查询块，放在任意编的目录中即可使用。
或将代码块粘贴到 `_research/XX_编名/_XX_编名_仪表盘.md` 中，在 Obsidian 打开即可。

## 时间取值优先级

| 优先级 | 条件 | 时间取值 | 地点列 | 刊名列 |
| --- | --- | --- | --- | --- |
| 1 | `create_y/m/d` 有年+月（或年+月+日） | 创建时间 | 填入 `location` | 填入 `publication`（若 location 为空则 publication 加括号） |
| 2 | 创建仅有年，但地点以 春/夏/秋/冬 开头 → 视同有月份 | 创建时间 | 填入 `location` | 填入 `publication`（若 location 为空则 publication 加括号） |
| 3 | 创建仅有年，刊载有年+月，且创建年=刊载年 | 改用刊载时间 | 填入 `location`（加括号） | 填入 `publication` |
| 4 | 创建全空，刊载有值 | 刊载时间 | 留空 | 填入 `publication` |
| 5 | 全无 | 「无日期」 | — | — |

有日期的文章按时间升序排列在前，无日期的排在末尾。