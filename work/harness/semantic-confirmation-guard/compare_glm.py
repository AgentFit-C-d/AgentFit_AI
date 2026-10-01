"""Only the classifier model changes; same frozen protocol and gold."""
from pathlib import Path
import compare

compare.MODEL = 'z-ai/glm-5.3'
compare.OUT = Path('E:/AgentFit/output/semantic-confirmation-guard-glm-v1')
compare.FILES += [Path(__file__), compare.ROOT / 'specs/ai-developer/semantic-confirmation-guard/glm-comparison-plan.md']

if __name__ == '__main__':
    compare.main()
