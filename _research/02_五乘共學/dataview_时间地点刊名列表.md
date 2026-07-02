
通用查询块，放在任意编的仪表盘 Markdown 文件中即可使用。

## 时间取值优先级

| 优先级 | 条件 | 时间取值 | 地点列 | 刊名列 |
|--------|------|----------|--------|--------|
| 1 | `create_y/m/d` 有值 | 创建时间 | 填入 `location` | 留空 |
| 3 | 创建仅有年，刊载至少有年+月 | 改用刊载时间 | 留空 | 填入 `publication` |
| 2 | 创建全空，刊载有值 | 刊载时间 | 留空 | 填入 `publication` |
| fallback | 旧格式 `date` 字段 | 直接使用 | 填入 `location` | 填入 `publication` |
| 4 | 全无 | 「无日期」 | - | - |

有日期的文章按时间升序排列在前，无日期的排在末尾。

## 代码块


```dataviewjs
const currentFolder = dv.current().file.folder;
const pages = dv.pages('"' + currentFolder + '"')
  .where(function(p) {
    var name = p.file.name;
    return name && name.indexOf('仪表盘') === -1 && name.indexOf('編目錄') === -1;
  });

var withDate = [];
var withoutDate = [];

for (var i = 0; i < pages.length; i++) {
  var page = pages[i];
  var cy = page.create_y || '';
  var cm = page.create_m || '';
  var cd = page.create_d || '';
  var py = page.publish_y || '';
  var pm = page.publish_m || '';
  var pd = page.publish_d || '';
  var location = page.location || '';
  var publication = page.publication || '';
  var legacyDate = page.date || '';

  var hasCreate = !!(cy || cm || cd);
  var hasPublish = !!(py || pm || pd);

  var time = '';
  var loc = '';
  var pub = '';

  if (hasCreate) {
    if (cy && !cm && !cd && py && pm) {
      time = py + (pm ? '.' + pm : '') + (pd ? '.' + pd : '');
      pub = publication;
    } else {
      time = cy + (cm ? '.' + cm : '') + (cd ? '.' + cd : '');
      loc = location;
    }
  } else if (hasPublish) {
    time = py + (pm ? '.' + pm : '') + (pd ? '.' + pd : '');
    pub = publication;
  } else if (legacyDate) {
    var parts = legacyDate.split('-');
    time = parts[0] + (parts[1] ? '.' + parts[1] : '');
    loc = location;
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

var rows = [];
for (var j = 0; j < withDate.length; j++) {
  var d = withDate[j];
  rows.push([d.time, d.loc, d.pub, d.link]);
}
for (var k = 0; k < withoutDate.length; k++) {
  var u = withoutDate[k];
  rows.push(['无日期', u.loc, u.pub, u.link]);
}

dv.table(['时间', '地点', '刊名', '文章名'], rows);
```

## 使用方式

将代码块粘贴到 `_research/XX_编名/_XX_编名_仪表盘.md` 中，在 Obsidian 打开即可。
