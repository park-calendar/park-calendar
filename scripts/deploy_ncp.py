#!/usr/bin/env python3
"""
NCP Object Storage 배포 (클라우드/로컬 공용, boto3 사용).

인증 우선순위
  1) 환경변수 NCP_ACCESS_KEY / NCP_SECRET_KEY
  2) 환경변수 AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
  3) AWS CLI 프로필 (NCP_PROFILE, 기본 'ncp')

사용법
  python3 scripts/deploy_ncp.py --bucket pjs.test          # index.html + data/ 업로드
  python3 scripts/deploy_ncp.py --bucket pjs.test data     # data/ 만 업로드 (루틴용)
  python3 scripts/deploy_ncp.py --bucket pjs.test pull     # 버킷 data/ → 로컬 data/ 내려받기
필요 패키지: pip install boto3
"""
import argparse, hashlib, os, sys

try:
    import boto3
    from botocore.config import Config
except ImportError:
    print("boto3 가 없습니다: pip install boto3", file=sys.stderr); sys.exit(2)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENDPOINT = os.environ.get("NCP_ENDPOINT", "https://kr.object.ncloudstorage.com")
REGION = os.environ.get("NCP_REGION", "kr-standard")


def client():
    ak = os.environ.get("NCP_ACCESS_KEY") or os.environ.get("AWS_ACCESS_KEY_ID")
    sk = os.environ.get("NCP_SECRET_KEY") or os.environ.get("AWS_SECRET_ACCESS_KEY")
    if ak and sk:
        session = boto3.session.Session(aws_access_key_id=ak, aws_secret_access_key=sk, region_name=REGION)
    else:
        session = boto3.session.Session(profile_name=os.environ.get("NCP_PROFILE", "ncp"), region_name=REGION)
    return session.client("s3", endpoint_url=ENDPOINT, config=Config(signature_version="s3v4"))


def md5(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def remote_etag(s3, bucket, key):
    try:
        return s3.head_object(Bucket=bucket, Key=key)["ETag"].strip('"')
    except Exception:
        return None


def put(s3, bucket, local, key, ctype, force=False):
    if not force and remote_etag(s3, bucket, key) == md5(local):
        print(f"  = {key} (변경 없음)"); return False
    with open(local, "rb") as f:
        s3.put_object(Bucket=bucket, Key=key, Body=f.read(), ACL="public-read",
                      ContentType=ctype, CacheControl="no-cache")
    print(f"  ↑ {key}"); return True


def pull(s3, bucket):
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    resp = s3.list_objects_v2(Bucket=bucket, Prefix="data/")
    n = 0
    for obj in resp.get("Contents", []):
        key = obj["Key"]
        if not key.endswith(".json"):
            continue
        local = os.path.join(ROOT, key)
        s3.download_file(bucket, key, local); n += 1
        print(f"  ↓ {key}")
    print(f"내려받기 완료: {n}개")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="all", choices=["all", "data", "pull"])
    ap.add_argument("--bucket", default=os.environ.get("NCP_BUCKET"))
    ap.add_argument("--force", action="store_true", help="ETag 가 같아도 다시 업로드")
    a = ap.parse_args()
    if not a.bucket:
        print("--bucket 또는 NCP_BUCKET 이 필요합니다", file=sys.stderr); sys.exit(2)
    s3 = client()
    print(f"▶ bucket={a.bucket} endpoint={ENDPOINT} mode={a.mode}")
    if a.mode == "pull":
        pull(s3, a.bucket); return
    changed = 0
    data_dir = os.path.join(ROOT, "data")
    for name in sorted(os.listdir(data_dir)):
        if name.endswith(".json"):
            changed += put(s3, a.bucket, os.path.join(data_dir, name), f"data/{name}", "application/json; charset=utf-8", a.force)
    if a.mode == "all":
        changed += put(s3, a.bucket, os.path.join(ROOT, "index.html"), "index.html", "text/html; charset=utf-8", a.force)
    print(f"✔ 완료: {changed}개 업로드")
    print(f"  {ENDPOINT}/{a.bucket}/index.html")


if __name__ == "__main__":
    main()
