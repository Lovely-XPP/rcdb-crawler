# rcdb-crawler
## Introduction

A crawler for rcdb.com. Crawler of the `Roller coaster` data.



## Data Format

### data

`json -> .xlsx`

```json
{
  id: int, // the No. of the website
  name: str, 
  location: str, 
  catalog: str,
  material: str,
  design: str,
  horror_degree: str,
  classification: str,
  height: str, // ft
  length: str, // ft
  speed: str, // mph
  drop: str, // ft
  inverse: str, 
  vertical_degree: str, // deg
  runtime: str,
  arrangement: str,
  joint: str,
  capacity: str, // people per hour
}
```



### figure

The `Roller coaster` fig will be save to:

```
<script_dir>/fig/<id>
```



