prepare-tools:
	mkdir -p .build
	# skaffold
	@test -f .build/skaffold || (curl -sL https://storage.googleapis.com/skaffold/releases/v2.0.0/skaffold-linux-amd64 --output .build/skaffold && chmod +x .build/skaffold)
	# kubectl
	@test -f .build/kubectl || (curl -sL https://dl.k8s.io/release/v1.25.0/bin/linux/amd64/kubectl --output .build/kubectl && chmod +x .build/kubectl)
	# k3d
	@test -f .build/k3d || (curl -sL https://github.com/k3d-io/k3d/releases/download/v5.4.6/k3d-linux-amd64 --output .build/k3d && chmod +x .build/k3d)
	# helm
	@test -f .build/helm || (curl -sL https://get.helm.sh/helm-v3.10.2-linux-amd64.tar.gz --output /tmp/helm.tar.gz && tar xf /tmp/helm.tar.gz -C /tmp && mv /tmp/linux-amd64/helm .build/helm && chmod +x .build/helm)
	# kubens
	@test -f .build/kubens || (curl -sL https://raw.githubusercontent.com/ahmetb/kubectx/master/kubens --output .build/kubens && chmod +x .build/kubens)
	# backup-repository server (for encoding passwords)
	@test -f .build/br || (curl -sL https://github.com/riotkit-org/backup-repository/releases/download/v4.0.0-rc17/backup-repository_4.0.0-rc17_linux_amd64.tar.gz --output /tmp/br.tar.gz && tar xf /tmp/br.tar.gz -C /tmp && mv /tmp/backup-repository .build/br && chmod +x .build/br)

fix-hosts:
	cat /etc/hosts | grep "bmt-registry" > /dev/null || (sudo /bin/bash -c "echo '127.0.0.1 bmt-registry' >> /etc/hosts")
	cat /etc/hosts | grep "bm-registry" > /dev/null || (sudo /bin/bash -c "echo '127.0.0.1 bm-registry' >> /etc/hosts")

.PHONY: test
test: prepare-tools fix-hosts
	PATH="$${PATH}":$$(pwd)/.build PYTHONPATH="$${PYTHONPATH}:$$(pwd)" pytest . -s
