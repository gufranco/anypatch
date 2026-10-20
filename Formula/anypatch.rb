class Anypatch < Formula
  include Language::Python::Virtualenv

  desc "Read, write, merge and convert binary patches in every documented format"
  homepage "https://github.com/gufranco/anypatch"
  url "https://github.com/gufranco/anypatch/archive/refs/tags/v0.4.0.tar.gz"
  sha256 "2248af77178fbdfaf3eadfd6be584e41556370b7b3bc6a8e6f8fc2c660fcd29f"
  license "MIT"
  head "https://github.com/gufranco/anypatch.git", branch: "main"

  depends_on "uv" => :build
  depends_on "python@3.14"

  def install
    python = formula_opt_bin("python@3.14")/"python3.14"
    ENV["UV_PROJECT_ENVIRONMENT"] = libexec
    ENV["UV_PYTHON_DOWNLOADS"] = "never"
    system "uv", "sync", "--frozen", "--no-dev", "--no-editable", "--extra", "cli",
           "--python", python
    bin.install_symlink libexec/"bin/anypatch"
  end

  test do
    assert_match "anypatch #{version}", shell_output("#{bin}/anypatch --version")

    report = shell_output("#{bin}/anypatch doctor")
    assert_match "zlib", report
    assert_match "lzma", report

    assert_match '"healthy": true', shell_output("#{bin}/anypatch doctor --json")
  end
end
