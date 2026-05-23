for ver in 3.8 3.9 3.10 3.11 3.12 3.13 3.14; do
  echo "Testing Python $ver..."
  uv run --python $ver python test.py
done
