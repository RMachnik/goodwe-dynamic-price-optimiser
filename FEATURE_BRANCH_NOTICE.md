# ⚠️ FEATURE BRANCH DEPLOYMENT NOTICE

## Current Status
This codebase is currently on the **`feature/cloud-migration`** branch, which has NOT been merged to `master` yet.

## Important Considerations for Deployment

### For Testing/Development Deployment
The deployment scripts are **ready to use** from this feature branch:
```bash
./scripts/deploy-hub-api.sh feature/cloud-migration
```

The script will:
- Detect you're on a feature branch
- Warn you and ask for confirmation
- Deploy the current branch code to VPS
- Tag the deployment with the branch name

### For Production Deployment
**Before deploying to production:**

1. **Merge to Master**
   ```bash
   git checkout master
   git merge feature/cloud-migration
   git push origin master
   ```

2. **Then Deploy**
   ```bash
   ./scripts/deploy-hub-api.sh master
   # or
   ./scripts/deploy-hub-api.sh  # defaults to current branch
   ```

### Script Behavior
- `deploy-hub-api.sh` now accepts an optional branch name parameter
- If no parameter provided, uses current branch
- Warns when deploying from non-master branches
- Records deployed branch in `DEPLOY_BRANCH.txt` on VPS for tracking

### Rollback Safety
The Raspberry Pi backup (`backup-rasp.sh`) captures the current master state, so:
- ✅ Safe to test feature branch on VPS
- ✅ Pi remains on stable master
- ✅ Can rollback VPS anytime
- ✅ No risk to production Pi system

## Testing Strategy

**Recommended Flow:**
1. Deploy feature branch to VPS for testing
2. Test thoroughly with mock nodes
3. Once confident, merge to master
4. Re-deploy from master for production use

**Git Commands Reference:**
```bash
# Check current branch
git branch --show-current

# List all branches
git branch -a

# Switch to master
git checkout master

# Merge feature branch
git merge feature/cloud-migration

# Push to remote
git push origin master
```
