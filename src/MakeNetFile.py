import click

@click.command()
@click.option("--sampdirs", help="equivalence class file")
@click.option("--netfile", help="output net file")
@click.option("--cutoff", default=10, help="filter contigs with fewer than this many reads")
@click.option("--writecomponents/--no-writecomponents", default=False, help="write out connected components as clusters")
def buildNetFromEq(sampdirs, netfile, cutoff, writecomponents):
    import itertools
    import pandas as pd
    import numpy as np
    import os

    sep = os.path.sep

    dirs = os.listdir(sampdirs)
    sampdirs = [sep.join([sampdirs, f]) for f in dirs]
    sffiles = [sep.join([sd, 'quant.sf']) for sd in sampdirs]

    quant = None
    for sffile in sffiles:
        if quant is None:
            quant = pd.read_table(sffile)
            quant.set_index('Name', inplace=True)
        else:
            quant2 = pd.read_table(sffile)
            quant2.set_index('Name', inplace=True)
            quant += quant2

    #quant.set_index('Name', inplace=True)

    tnames = []
    weightDict = {}
    diagCounts = np.zeros(len(quant['TPM'].values))

    tot = 0

    eqfiles = [sep.join([sd, 'aux/eq_classes.txt']) for sd in sampdirs]

    firstSamp = True
    numSamp = 0
    eqClasses = {}
    for eqfile in eqfiles:
        with open(eqfile) as ifile:
            numSamp += 1
            numTran = int(ifile.readline().rstrip())
            numEq = int(ifile.readline().rstrip())
            print("file: {}; # tran = {}; # eq = {}".format(eqfile, numTran, numEq))
            if firstSamp:
                for i in xrange(numTran):
                    tnames.append(ifile.readline().rstrip())
            else:
                for i in xrange(numTran):
                    ifile.readline()

            for i in xrange(numEq):
                toks = map(int, ifile.readline().rstrip().split('\t'))
                nt = toks[0]
                tids = tuple(toks[1:-1])
                count = toks[-1]
                if tids in eqClasses:
                    eqClasses[tids] += count
                else:
                    eqClasses[tids] = count

            firstSamp = False

    tpm = quant.loc[tnames, 'TPM'].values / numSamp
    estCount = quant.loc[tnames, 'NumReads'].values
    efflens = quant.loc[tnames, 'EffectiveLength'].values
    epsilon =  np.finfo(float).eps
    for tids, count in eqClasses.iteritems():
        denom = sum([tpm[t] for t in tids])
        tot += count
        for t1, t2 in itertools.combinations(tids,2):
            #tpm1 = tpm[t1]
            #tpm2 = tpm[t2]
            #w = count * ((tpm1 + tpm2) / denom)
            if (t1, t2) in weightDict:
                weightDict[(t1, t2)] += count
            else:
                weightDict[(t1, t2)] = count
        for t in tids:
            #if (estCount[t] <= cutoff):
            #    continue
            #diagCounts[t] += count * (tpm[t] / denom)
            diagCounts[t] += count


    print("total reads = {}".format(tot))
    maxWeight = 0.0
    prior = 0.1
    edgesToRemove = []
    for k,v in weightDict.iteritems():
        c0, c1 = diagCounts[k[0]], diagCounts[k[1]]
        #w = (v + prior) / (min(c0, c1) + prior)
        if c0 + c1 > epsilon and c0 > cutoff and c1 > cutoff:
            w = v / min(c0, c1)
            weightDict[k] = w
            if w > maxWeight:
                maxWeight = w
        else:
            edgesToRemove.append(k)

    for e in edgesToRemove:
        del weightDict[e]

    tnamesFilt = []
    relabel = {}
    for i in xrange(len(estCount)):
        if (diagCounts[i] > cutoff):
            relabel[i] = len(tnamesFilt)
            tnamesFilt.append(tnames[i])
            weightDict[(i, i)] = 1.1

    import networkx as nx
    G = nx.Graph() if writecomponents else None
    with open(netfile, 'w') as ofile:
        writeEdgeList(weightDict, tnames, ofile, G)

    if G is not None:
        clustFile = netfile.split('.net')[0] + '.clust'
        print("Writing connected components as clusters to {}".format(clustFile))
        with open(clustFile, 'w') as ofile:
            cc = nx.connected_component_subgraphs(G)
            for c in cc:
                ofile.write('{}\n'.format('\t'.join(c.nodes())))

def writeEdgeList(weightDict, tnames, ofile, G):
    useGraph = G is not None
    for k,v in weightDict.iteritems():
        ofile.write("{}\t{}\t{}\n".format(tnames[k[0]], tnames[k[1]], v))
        if useGraph:
            G.add_edge(tnames[k[0]], tnames[k[1]])


def writePajek(weightDict, tnames, relabel, ofile):
    with open(netfile, 'w') as ofile:
        ofile.write("*Vertices\t{}\n".format(len(tnamesFilt)))
        for i, n in enumerate(tnamesFilt):
            ofile.write("{}\t\"{}\"\n".format(i, n))
        ofile.write("*Edges\n")
        print("There are {} edges\n".format(len(weightDict)))
        for k,v in weightDict.iteritems():
            ofile.write("{}\t{}\t{}\n".format(relabel[k[0]], relabel[k[1]], v))
            #ofile.write("{}\t{}\t{}\n".format(tnames[k[0]], tnames[k[1]], v))
            #if k[0] != k[1]:
            #    ofile.write("{}\t{}\t{}\n".format(tnames[k[1]], tnames[k[0]], v))


if __name__ == "__main__":
    import sys
    buildNetFromEq()
