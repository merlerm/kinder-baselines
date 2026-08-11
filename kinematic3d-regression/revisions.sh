#!/usr/bin/env bash

# Shared immutable revision manifest for the validation scripts.

get_kindergarden_revision() {
  case "$1" in
    A0) echo "421609e" ;;
    A1) echo "4e9a443" ;;
    A2) echo "9bf8d0f" ;;
    A3) echo "486f303" ;;
    A4) echo "8486999" ;;
    *)
      echo "Unknown revision label: $1" >&2
      return 2
      ;;
  esac
}

