#include <linux/module.h>
#include <linux/pci.h>
#include <linux/delay.h>
#include <linux/kernel.h>

#define NVIDIA_VENDOR 0x10de
#define RTX5090_DEVICE 0x2b85
#define INTEL_VENDOR 0x8086
#define BARLOW_5786 0x5786

static struct pci_dev *gpu;
static struct pci_dev *bridge;
static int reassert_value;

static void dump_state(const char *tag)
{
	u16 ctl2 = 0, sta = 0;
	pcie_capability_read_word(bridge, PCI_EXP_LNKCTL2, &ctl2);
	pcie_capability_read_word(bridge, PCI_EXP_LNKSTA, &sta);
	pr_info("tb5_gen3: %s LnkCtl2=%04x LnkSta=%04x\n", tag, ctl2, sta);
}

static int target_gen3_hasd(void)
{
	u16 ctl2;
	int ret;

	ret = pcie_capability_read_word(bridge, PCI_EXP_LNKCTL2, &ctl2);
	if (ret)
		return ret;

	ctl2 &= ~(PCI_EXP_LNKCTL2_TLS | PCI_EXP_LNKCTL2_HASD);
	ctl2 |= 3 | PCI_EXP_LNKCTL2_HASD;

	ret = pcie_capability_write_word(bridge, PCI_EXP_LNKCTL2, ctl2);
	if (ret)
		return ret;

	pcie_capability_read_word(bridge, PCI_EXP_LNKCTL2, &ctl2);
	if ((ctl2 & PCI_EXP_LNKCTL2_TLS) != 3 ||
	    !(ctl2 & PCI_EXP_LNKCTL2_HASD))
		return -EIO;

	return 0;
}

static bool link_is_gen4_x4(void)
{
	u16 sta = 0, ctl2 = 0;
	pcie_capability_read_word(bridge, PCI_EXP_LNKSTA, &sta);
	pcie_capability_read_word(bridge, PCI_EXP_LNKCTL2, &ctl2);

	return ((ctl2 & PCI_EXP_LNKCTL2_TLS) == 4 &&
		(sta & PCI_EXP_LNKSTA_CLS) == 4 &&
		((sta & PCI_EXP_LNKSTA_NLW) >> 4) == 4 &&
		!(sta & PCI_EXP_LNKSTA_LT) &&
		(sta & PCI_EXP_LNKSTA_DLLLA));
}

static bool link_is_gen3_x4(void)
{
	u16 sta = 0, ctl2 = 0;
	pcie_capability_read_word(bridge, PCI_EXP_LNKSTA, &sta);
	pcie_capability_read_word(bridge, PCI_EXP_LNKCTL2, &ctl2);

	return ((ctl2 & PCI_EXP_LNKCTL2_TLS) == 3 &&
		(ctl2 & PCI_EXP_LNKCTL2_HASD) &&
		(sta & PCI_EXP_LNKSTA_CLS) == 3 &&
		((sta & PCI_EXP_LNKSTA_NLW) >> 4) == 4 &&
		!(sta & PCI_EXP_LNKSTA_LT) &&
		(sta & PCI_EXP_LNKSTA_DLLLA));
}

static int do_reassert(const char *val, const struct kernel_param *kp)
{
	int v, ret;
	ret = kstrtoint(val, 0, &v);
	if (ret)
		return ret;
	if (v != 1)
		return -EINVAL;
	if (!bridge)
		return -ENODEV;

	ret = target_gen3_hasd();
	if (ret)
		return ret;

	reassert_value = 1;
	dump_state("post-NVIDIA reassert");
	return 0;
}

static int get_reassert(char *buf, const struct kernel_param *kp)
{
	return sysfs_emit(buf, "%d\n", reassert_value);
}

static const struct kernel_param_ops reassert_ops = {
	.set = do_reassert,
	.get = get_reassert,
};

module_param_cb(reassert, &reassert_ops, &reassert_value, 0600);

static int __init tb5_gen3_init(void)
{
	u16 ctl;
	int i, stable = 0, ret;

	gpu = pci_get_domain_bus_and_slot(0, 0x8d, PCI_DEVFN(0, 0));
	if (!gpu)
		return -ENODEV;

	if (gpu->vendor != NVIDIA_VENDOR || gpu->device != RTX5090_DEVICE) {
		ret = -ENODEV;
		goto fail_gpu;
	}

	if (gpu->driver) {
		ret = -EBUSY;
		goto fail_gpu;
	}

	bridge = gpu->bus->self;
	if (!bridge || bridge->vendor != INTEL_VENDOR || bridge->device != BARLOW_5786) {
		ret = -ENODEV;
		goto fail_gpu;
	}

	pci_dev_get(bridge);
	dump_state("initial");

	for (i = 0; i < 20; i++) {
		if (link_is_gen4_x4())
			stable++;
		else
			stable = 0;
		if (stable >= 5)
			break;
		msleep(100);
	}

	if (stable < 5) {
		ret = -EAGAIN;
		goto fail_bridge;
	}

	ret = target_gen3_hasd();
	if (ret)
		goto fail_bridge;

	dump_state("Gen3+HASD armed");

	ret = pcie_capability_read_word(bridge, PCI_EXP_LNKCTL, &ctl);
	if (ret)
		goto fail_bridge;

	ctl |= PCI_EXP_LNKCTL_RL;
	ret = pcie_capability_write_word(bridge, PCI_EXP_LNKCTL, ctl);
	if (ret)
		goto fail_bridge;

	pr_info("tb5_gen3: single pre-NVIDIA Gen3 retrain requested\n");

	stable = 0;
	for (i = 0; i < 200; i++) {
		if (link_is_gen3_x4())
			stable++;
		else
			stable = 0;
		if (stable >= 5)
			break;
		msleep(100);
	}

	if (stable < 5) {
		ret = -ETIMEDOUT;
		goto fail_bridge;
	}

	dump_state("Gen3 stable");
	msleep(2000);

	if (!link_is_gen3_x4()) {
		ret = -EIO;
		goto fail_bridge;
	}

	pr_info("tb5_gen3: SUCCESS: stable Gen3 x4 + HASD before NVIDIA\n");
	return 0;

fail_bridge:
	pci_dev_put(bridge);
	bridge = NULL;
fail_gpu:
	pci_dev_put(gpu);
	gpu = NULL;
	return ret;
}

static void __exit tb5_gen3_exit(void)
{
	if (bridge)
		pci_dev_put(bridge);
	if (gpu)
		pci_dev_put(gpu);
}

module_init(tb5_gen3_init);
module_exit(tb5_gen3_exit);

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Guarded RTX 5090 / Barlow Ridge Gen3 pre-NVIDIA stabilizer");
MODULE_AUTHOR("local diagnostic helper");
