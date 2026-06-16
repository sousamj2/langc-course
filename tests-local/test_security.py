from app.security import SecurityPipeline

def test_check_input_masks_email():
    pipeline = SecurityPipeline()
    is_allowed, cleaned, notes = pipeline.check_input("Send me a test email to test@gmail.com.")
    
    assert is_allowed is True
    assert "test@gmail.com" not in cleaned
    assert "[EMAIL REDACTED]" in cleaned
    assert "Input PII masked: ['email']" in notes
