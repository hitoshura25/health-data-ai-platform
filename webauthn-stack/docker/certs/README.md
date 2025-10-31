# mTLS Certificates

Auto-generated certificates for zero-trust mTLS communication.

## Certificate Authority (CA)
- `ca-cert.pem` - CA certificate (public, trusted by all services)
- `ca-key.pem` - CA private key (used to sign service certificates)

## Envoy Gateway
- `gateway-cert.pem` - Gateway certificate (signed by CA)
- `gateway-key.pem` - Gateway private key

## Example Service
- `service-cert.pem` - Service certificate (signed by CA)
- `service-key.pem` - Service private key

## Validity
All certificates are valid for 365 days from generation.

## Rotation
To rotate certificates, delete this directory and regenerate the client.

## Security Notes
- ⚠️ DO NOT commit `.pem` files to version control
- ⚠️ Private keys (`*-key.pem`) must be kept secure
- ✅ Certificates are automatically ignored by git
- ✅ Each generation creates unique certificates
